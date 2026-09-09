from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from games_intel.db.exceptions import GameNotFoundError
from games_intel.db.mapping import game_list_item, game_record, utcnow
from games_intel.db.models import Game, GamePlatform
from games_intel.db.records import CatalogSlice, GameListPage, GameRecord
from games_intel.db.types import GameSort, InsertOutcome, SortOrder


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class GameCatalogRepository:
    """Writes catalog columns and platforms. Does not touch reviews/letsplay/embedding."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_game_stub(
        self,
        *,
        metacritic_slug: str,
        title: str,
        listing_url: str | None = None,
    ) -> tuple[UUID, InsertOutcome]:
        stmt = (
            insert(Game)
            .values(
                metacritic_slug=metacritic_slug,
                title=title,
                listing_url=listing_url,
                genres=[],
                updated_at=utcnow(),
            )
            .on_conflict_do_nothing(index_elements=[Game.metacritic_slug])
            .returning(Game.id)
        )
        inserted_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if inserted_id is not None:
            return inserted_id, InsertOutcome.inserted
        existing = await self._session.scalar(
            select(Game.id).where(Game.metacritic_slug == metacritic_slug)
        )
        if existing is None:
            msg = "stub conflict but game missing"
            raise RuntimeError(msg)
        return existing, InsertOutcome.duplicate

    async def upsert_catalog(self, slice_: CatalogSlice) -> UUID:
        now = utcnow()
        stmt = (
            insert(Game)
            .values(
                metacritic_slug=slice_.metacritic_slug,
                title=slice_.title,
                listing_url=slice_.listing_url,
                cover_url=slice_.cover_url,
                cover_source_url=slice_.cover_source_url,
                developer=slice_.developer,
                publisher=slice_.publisher,
                genres=list(slice_.genres),
                release_date=slice_.release_date,
                description=slice_.description,
                video_url=slice_.video_url,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[Game.metacritic_slug],
                set_={
                    "title": slice_.title,
                    "listing_url": slice_.listing_url,
                    "cover_url": slice_.cover_url,
                    "cover_source_url": slice_.cover_source_url,
                    "developer": slice_.developer,
                    "publisher": slice_.publisher,
                    "genres": list(slice_.genres),
                    "release_date": slice_.release_date,
                    "description": slice_.description,
                    "video_url": slice_.video_url,
                    "updated_at": now,
                },
            )
            .returning(Game.id)
        )
        game_id = (await self._session.execute(stmt)).scalar_one()
        await self._session.execute(delete(GamePlatform).where(GamePlatform.game_id == game_id))
        if slice_.platforms:
            self._session.add_all(
                [
                    GamePlatform(
                        game_id=game_id,
                        platform_code=platform.platform_code,
                        metascore=platform.metascore,
                        userscore=platform.userscore,
                    )
                    for platform in slice_.platforms
                ]
            )
        await self._session.flush()
        return game_id

    async def get_by_slug(self, metacritic_slug: str) -> GameRecord | None:
        game = await self._session.scalar(
            select(Game)
            .options(selectinload(Game.platforms))
            .where(Game.metacritic_slug == metacritic_slug)
        )
        if game is None:
            return None
        return game_record(game)

    async def require_id(self, metacritic_slug: str) -> UUID:
        game_id = await self._session.scalar(
            select(Game.id).where(Game.metacritic_slug == metacritic_slug)
        )
        if game_id is None:
            raise GameNotFoundError(metacritic_slug)
        return game_id

    async def list_games(
        self,
        *,
        q: str | None = None,
        platform: str | None = None,
        sort: GameSort = GameSort.metascore,
        order: SortOrder = SortOrder.desc,
        page: int = 1,
        page_size: int = 20,
    ) -> GameListPage:
        page = max(page, 1)
        page_size = max(page_size, 1)
        filters = []
        if q:
            pattern = f"%{_escape_like(q)}%"
            filters.append(Game.title.ilike(pattern, escape="\\"))
        if platform:
            filters.append(
                Game.id.in_(
                    select(GamePlatform.game_id).where(GamePlatform.platform_code == platform)
                )
            )

        count_stmt = select(func.count()).select_from(Game)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = int(await self._session.scalar(count_stmt) or 0)

        max_metascore = func.max(GamePlatform.metascore)
        max_userscore = func.max(GamePlatform.userscore)
        stmt = (
            select(Game, max_metascore, max_userscore)
            .outerjoin(GamePlatform, GamePlatform.game_id == Game.id)
            .group_by(Game.id)
        )
        if filters:
            stmt = stmt.where(*filters)

        descending = order is SortOrder.desc
        sort_map: dict[GameSort, Any] = {
            GameSort.metascore: max_metascore,
            GameSort.userscore: max_userscore,
            GameSort.title: Game.title,
            GameSort.updated: Game.updated_at,
        }
        sort_column = sort_map[sort]
        primary = sort_column.desc() if descending else sort_column.asc()
        if sort in {GameSort.metascore, GameSort.userscore}:
            primary = primary.nulls_last()
        stmt = stmt.order_by(primary, Game.metacritic_slug.asc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        rows = (await self._session.execute(stmt)).all()
        game_ids = [game.id for game, _meta, _user in rows]
        platform_map = await self._platform_codes(game_ids)
        items = tuple(
            game_list_item(
                game,
                max_metascore=meta,
                max_userscore=Decimal(user) if user is not None else None,
                platform_codes=platform_map.get(game.id, ()),
            )
            for game, meta, user in rows
        )
        return GameListPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
        )

    async def list_platform_codes(self) -> tuple[str, ...]:
        stmt = select(GamePlatform.platform_code).distinct().order_by(GamePlatform.platform_code)
        result = await self._session.scalars(stmt)
        return tuple(result.all())

    async def _platform_codes(self, game_ids: list[UUID]) -> dict[UUID, tuple[str, ...]]:
        if not game_ids:
            return {}
        stmt = (
            select(GamePlatform.game_id, GamePlatform.platform_code)
            .where(GamePlatform.game_id.in_(game_ids))
            .order_by(GamePlatform.platform_code)
        )
        grouped: dict[UUID, list[str]] = {game_id: [] for game_id in game_ids}
        for game_id, code in (await self._session.execute(stmt)).all():
            grouped[game_id].append(code)
        return {game_id: tuple(codes) for game_id, codes in grouped.items()}
