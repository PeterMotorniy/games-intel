from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.adapters.media.port import CoverStorage
from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.port import MetacriticPort
from games_intel.contracts.adapters import GameDetails, GetGameInput
from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.ids import new_traceparent
from games_intel.contracts.payloads import GameCataloged, GameListed, ListedGame, PlatformScore
from games_intel.db.records import CatalogSlice, OutboxInsert, PlatformScoreRecord
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage
from games_intel.kafka.classify import map_adapter_error
from games_intel.kafka.exceptions import NotFoundError
from games_intel.kafka.logging import emit_json
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.workers.catalog")

_WORKER_TYPE = "catalog"


@dataclass(frozen=True, slots=True)
class _CatalogPrepared:
    listed: GameListed
    details: GameDetails
    cover_url: str | None


class CatalogHandler:
    """Catalog one discovered game, then emit game.cataloged."""

    def __init__(self, settings: Settings, port: MetacriticPort, covers: CoverStorage) -> None:
        self.settings = settings
        self.port = port
        self.covers = covers

    async def prepare(self, event: CloudEvent[Any]) -> _CatalogPrepared:
        listed = event.data
        if not isinstance(listed, GameListed):
            msg = "catalog expected GameListed payload"
            raise TypeError(msg)
        details = await self._get_game(listed.game.metacritic_slug)
        cover_url = await self._store_cover(listed.game.metacritic_slug, details.cover_bytes)
        self._warn_optional_gaps(listed.game.metacritic_slug, details)
        return _CatalogPrepared(listed=listed, details=details, cover_url=cover_url)

    async def persist(
        self, event: CloudEvent[Any], session: AsyncSession, prepared: _CatalogPrepared
    ) -> None:
        ingestion = IngestionRepository(session)
        catalog = GameCatalogRepository(session)
        listed = prepared.listed
        game = listed.game
        slice_ = _catalog_slice(game, prepared.details, prepared.cover_url)
        game_id = await catalog.upsert_catalog(slice_)
        await ingestion.upsert_item(
            run_id=listed.run_id,
            metacritic_slug=game.metacritic_slug,
            process_date=listed.process_date,
            stage=IngestionStage.cataloged,
            status=IngestionItemStatus.completed,
            game_id=game_id,
            event_id=event.id,
        )
        await ingestion.record_daily_processed_slug(listed.process_date, game.metacritic_slug)
        await _enqueue_game_cataloged(
            session,
            self.settings,
            listed=listed,
            details=prepared.details,
            cover_url=prepared.cover_url,
        )

    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None:
        prepared = await self.prepare(event)
        await self.persist(event, session, prepared)

    async def on_terminal_failure(
        self,
        event: CloudEvent[Any],
        session: AsyncSession,
        exc: BaseException,
    ) -> None:
        listed = event.data
        if not isinstance(listed, GameListed) or not isinstance(exc, NotFoundError):
            return
        await IngestionRepository(session).record_daily_processed_slug(
            listed.process_date, listed.game.metacritic_slug
        )

    async def _get_game(self, slug: str) -> GameDetails:
        try:
            return await self.port.get_game(GetGameInput(slug=slug))
        except MetacriticAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc

    async def _store_cover(self, slug: str, cover_bytes: bytes | None) -> str | None:
        if cover_bytes is None:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=slug,
                worker=_WORKER_TYPE,
                stage=self.settings.catalog.stage_name,
                event="cover_missing",
            )
            return None
        url = await self.covers.save(slug, cover_bytes)
        if url is None:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=slug,
                worker=_WORKER_TYPE,
                stage=self.settings.catalog.stage_name,
                event="cover_rejected",
            )
        return url

    def _warn_optional_gaps(self, slug: str, details: GameDetails) -> None:
        if details.video_url is None:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=slug,
                worker=_WORKER_TYPE,
                stage=self.settings.catalog.stage_name,
                event="video_missing",
                empty_video_ok=self.settings.catalog.empty_video_ok,
            )
        if details.developer is None:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=slug,
                worker=_WORKER_TYPE,
                stage=self.settings.catalog.stage_name,
                event="developer_missing",
            )


def _catalog_slice(listed: ListedGame, details: GameDetails, cover_url: str | None) -> CatalogSlice:
    return CatalogSlice(
        metacritic_slug=listed.metacritic_slug,
        title=details.title.strip() or listed.title,
        listing_url=str(listed.listing_url),
        cover_url=cover_url,
        cover_source_url=_optional_url(details.cover_source_url),
        developer=details.developer,
        publisher=details.publisher,
        genres=tuple(details.genres),
        release_date=details.release_date,
        description=details.description,
        video_url=_optional_url(details.video_url),
        platforms=tuple(_platform_record(item) for item in details.platforms),
    )


def _optional_url(value: HttpUrl | None) -> str | None:
    return None if value is None else str(value)


def _platform_record(item: PlatformScore) -> PlatformScoreRecord:
    userscore = None if item.userscore is None else Decimal(str(item.userscore))
    return PlatformScoreRecord(
        platform_code=item.platform_code,
        metascore=item.metascore,
        userscore=userscore,
    )


async def _enqueue_game_cataloged(
    session: AsyncSession,
    settings: Settings,
    *,
    listed: GameListed,
    details: GameDetails,
    cover_url: str | None,
) -> None:
    game = listed.game
    payload = GameCataloged(
        run_id=listed.run_id,
        process_date=listed.process_date,
        metacritic_slug=game.metacritic_slug,
        title=details.title,
        cover_url=cover_url,
        cover_source_url=details.cover_source_url,
        developer=details.developer,
        publisher=details.publisher,
        genres=list(details.genres),
        release_date=details.release_date,
        description=details.description,
        video_url=details.video_url,
        platforms=list(details.platforms),
    )
    event = build_cloud_event(
        settings,
        settings.catalog.publish_event,
        source=worker_source(settings, _WORKER_TYPE),
        subject=game.metacritic_slug,
        data=payload,
        stage=settings.catalog.stage_name,
        run_id=listed.run_id,
        traceparent=new_traceparent(),
    )
    await OutboxRepository(session).insert(
        OutboxInsert(
            producer=_WORKER_TYPE,
            idempotency_key=event.idempotencykey,
            topic=settings.event_name(settings.catalog.publish_event),
            partition_key=game.metacritic_slug,
            payload=cloud_event_to_dict(event),
        )
    )
