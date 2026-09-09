from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from games_intel.db.exceptions import GameNotFoundError, SimilarGameSelfReferenceError
from games_intel.db.mapping import similar_record, similarity_game, utcnow
from games_intel.db.models import Game, SimilarGame
from games_intel.db.records import SimilarGameRecord, SimilarityGame, SimilarNeighbor


class SimilarGamesRepository:
    """SimilarityWorker writer: embeddings and replace of similar_games sets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_embedding(
        self,
        *,
        game_id: UUID,
        embedding: Sequence[float],
        input_hash: str,
    ) -> None:
        stmt = (
            update(Game)
            .where(Game.id == game_id)
            .values(
                embedding=list(embedding),
                embedding_input_hash=input_hash,
                updated_at=utcnow(),
            )
            .returning(Game.id)
        )
        updated_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if updated_id is None:
            raise GameNotFoundError(str(game_id))

    async def upsert_embedding_by_slug(
        self,
        metacritic_slug: str,
        *,
        embedding: Sequence[float],
        input_hash: str,
    ) -> UUID:
        stmt = (
            update(Game)
            .where(Game.metacritic_slug == metacritic_slug)
            .values(
                embedding=list(embedding),
                embedding_input_hash=input_hash,
                updated_at=utcnow(),
            )
            .returning(Game.id)
        )
        updated_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if updated_id is None:
            raise GameNotFoundError(metacritic_slug)
        return updated_id

    async def get_similarity_game(self, metacritic_slug: str) -> SimilarityGame | None:
        game = await self._session.scalar(
            select(Game)
            .options(selectinload(Game.platforms))
            .where(Game.metacritic_slug == metacritic_slug)
        )
        if game is None:
            return None
        return similarity_game(game)

    async def list_all_games(self) -> tuple[SimilarityGame, ...]:
        stmt = (
            select(Game).options(selectinload(Game.platforms)).order_by(Game.metacritic_slug.asc())
        )
        rows = (await self._session.scalars(stmt)).all()
        return tuple(similarity_game(game) for game in rows)

    async def list_embedded_games(self) -> tuple[SimilarityGame, ...]:
        stmt = (
            select(Game)
            .options(selectinload(Game.platforms))
            .where(Game.embedding.is_not(None))
            .order_by(Game.metacritic_slug.asc())
        )
        rows = (await self._session.scalars(stmt)).all()
        return tuple(similarity_game(game) for game in rows)

    async def count_embedded(self) -> int:
        stmt = select(func.count()).select_from(Game).where(Game.embedding.is_not(None))
        return int(await self._session.scalar(stmt) or 0)

    async def neighbor_slugs(self, game_id: UUID) -> tuple[str, ...]:
        stmt = (
            select(Game.metacritic_slug)
            .join(SimilarGame, Game.id == SimilarGame.similar_game_id)
            .where(SimilarGame.game_id == game_id)
            .order_by(SimilarGame.rank.asc(), Game.metacritic_slug.asc())
        )
        return tuple((await self._session.scalars(stmt)).all())

    async def nearest_slugs_by_vector(
        self,
        embedding: Sequence[float],
        *,
        limit: int,
        exclude_game_id: UUID,
    ) -> tuple[str, ...]:
        if limit <= 0:
            return ()
        vector = list(embedding)
        stmt = (
            select(Game.metacritic_slug)
            .where(Game.embedding.is_not(None), Game.id != exclude_game_id)
            .order_by(Game.embedding.cosine_distance(vector), Game.metacritic_slug.asc())
            .limit(limit)
        )
        return tuple((await self._session.scalars(stmt)).all())

    async def replace_for_game(self, game_id: UUID, items: Sequence[SimilarNeighbor]) -> None:
        await self._session.execute(delete(SimilarGame).where(SimilarGame.game_id == game_id))
        await self._insert_neighbors(game_id, items)

    async def replace_all(self, items_by_game: Mapping[UUID, Sequence[SimilarNeighbor]]) -> None:
        await self._session.execute(delete(SimilarGame))
        for game_id, items in items_by_game.items():
            await self._insert_neighbors(game_id, items)

    async def list_for_slug(self, metacritic_slug: str) -> tuple[SimilarGameRecord, ...]:
        game_id = await self._session.scalar(
            select(Game.id).where(Game.metacritic_slug == metacritic_slug)
        )
        if game_id is None:
            raise GameNotFoundError(metacritic_slug)
        stmt = (
            select(SimilarGame, Game.metacritic_slug, Game.title)
            .join(Game, Game.id == SimilarGame.similar_game_id)
            .where(SimilarGame.game_id == game_id)
            .order_by(SimilarGame.rank.asc(), Game.metacritic_slug.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return tuple(similar_record(slug, title, row) for row, slug, title in rows)

    async def _insert_neighbors(self, game_id: UUID, items: Sequence[SimilarNeighbor]) -> None:
        if not items:
            return
        self._session.add_all(
            [
                SimilarGame(
                    game_id=game_id,
                    similar_game_id=item.similar_game_id,
                    score=item.score,
                    score_vector=item.score_vector,
                    rank=item.rank,
                )
                for item in items
            ]
        )
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if "ck_similar_games_no_self" in str(exc):
                raise SimilarGameSelfReferenceError(game_id) from exc
            raise
