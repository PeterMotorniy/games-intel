from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from sqlalchemy import func, select

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.factory import create_metacritic_port
from games_intel.contracts.adapters import GetGameInput
from games_intel.db.engine import create_engine, create_session_factory
from games_intel.db.models import Game, GamePlatform
from games_intel.db.records import CatalogSlice, PlatformScoreRecord
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.settings import load_settings

logger = logging.getLogger("games_intel.refresh_catalog")


def _slice(game: Game, details) -> CatalogSlice:
    return CatalogSlice(
        metacritic_slug=game.metacritic_slug,
        title=details.title.strip() or game.title,
        listing_url=game.listing_url,
        cover_url=game.cover_url,
        cover_source_url=(
            str(details.cover_source_url) if details.cover_source_url else game.cover_source_url
        ),
        developer=details.developer,
        publisher=details.publisher or game.publisher,
        genres=tuple(details.genres) or tuple(game.genres or ()),
        release_date=details.release_date or game.release_date,
        description=details.description or game.description,
        video_url=str(details.video_url) if details.video_url else game.video_url,
        platforms=tuple(
            PlatformScoreRecord(
                platform_code=row.platform_code,
                metascore=row.metascore,
                userscore=None if row.userscore is None else Decimal(str(row.userscore)),
            )
            for row in details.platforms
        ),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    port = create_metacritic_port(settings)
    async with factory() as session:
        scored = select(GamePlatform.game_id).where(GamePlatform.userscore.is_not(None))
        games = list(
            (
                await session.scalars(
                    select(Game)
                    .where(Game.id.not_in(scored))
                    .outerjoin(GamePlatform, GamePlatform.game_id == Game.id)
                    .group_by(Game.id)
                    .order_by(func.max(GamePlatform.metascore).desc().nulls_last(), Game.metacritic_slug)
                )
            ).all()
        )
    logger.info("refreshing %s games without userscore", len(games))
    ok = 0
    skipped = 0
    for game in games:
        try:
            details = await port.get_game(GetGameInput(slug=game.metacritic_slug))
        except (MetacriticAdapterError, Exception) as exc:
            logger.warning("skip %s: %s", game.metacritic_slug, exc)
            skipped += 1
            continue
        async with factory() as session:
            async with session.begin():
                await GameCatalogRepository(session).upsert_catalog(_slice(game, details))
        ok += 1
        if ok % 10 == 0:
            logger.info("updated %s / %s", ok, len(games))
    close = getattr(port, "aclose", None)
    if close is not None:
        await close()
    await engine.dispose()
    logger.info("done updated=%s skipped=%s", ok, skipped)


if __name__ == "__main__":
    asyncio.run(main())
