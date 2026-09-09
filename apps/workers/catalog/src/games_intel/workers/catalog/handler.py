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
from games_intel.contracts.payloads import (
    GameCataloged,
    GamesPageListed,
    ListedGame,
    PlatformScore,
)
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
class _CatalogGameSuccess:
    listed: ListedGame
    details: GameDetails
    cover_url: str | None


@dataclass(frozen=True, slots=True)
class _CatalogPrepared:
    page: GamesPageListed
    successes: tuple[_CatalogGameSuccess, ...]
    missing: tuple[ListedGame, ...]


class CatalogHandler:
    """Load every card on a listed page in one task, then fan-out per-game events."""

    def __init__(self, settings: Settings, port: MetacriticPort, covers: CoverStorage) -> None:
        self.settings = settings
        self.port = port
        self.covers = covers

    async def prepare(self, event: CloudEvent[Any]) -> _CatalogPrepared:
        page = event.data
        if not isinstance(page, GamesPageListed):
            msg = "catalog expected GamesPageListed payload"
            raise TypeError(msg)
        successes: list[_CatalogGameSuccess] = []
        missing: list[ListedGame] = []
        for listed in page.games:
            try:
                details = await self._get_game(listed.metacritic_slug)
            except NotFoundError:
                missing.append(listed)
                continue
            cover_url = await self._store_cover(listed.metacritic_slug, details.cover_bytes)
            self._warn_optional_gaps(listed.metacritic_slug, details)
            successes.append(
                _CatalogGameSuccess(listed=listed, details=details, cover_url=cover_url)
            )
        return _CatalogPrepared(page=page, successes=tuple(successes), missing=tuple(missing))

    async def persist(
        self, event: CloudEvent[Any], session: AsyncSession, prepared: _CatalogPrepared
    ) -> None:
        ingestion = IngestionRepository(session)
        catalog = GameCatalogRepository(session)
        for listed in prepared.missing:
            await ingestion.upsert_item(
                run_id=prepared.page.run_id,
                metacritic_slug=listed.metacritic_slug,
                process_date=prepared.page.process_date,
                stage=IngestionStage.cataloged,
                status=IngestionItemStatus.failed,
                event_id=event.id,
                error_type=NotFoundError.__name__,
                error_message="game card not found",
            )
        for item in prepared.successes:
            slice_ = _catalog_slice(item.listed, item.details, item.cover_url)
            game_id = await catalog.upsert_catalog(slice_)
            await ingestion.upsert_item(
                run_id=prepared.page.run_id,
                metacritic_slug=item.listed.metacritic_slug,
                process_date=prepared.page.process_date,
                stage=IngestionStage.cataloged,
                status=IngestionItemStatus.completed,
                game_id=game_id,
                event_id=event.id,
            )
            await _enqueue_game_cataloged(
                session,
                self.settings,
                page=prepared.page,
                listed=item.listed,
                details=item.details,
                cover_url=item.cover_url,
            )

    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None:
        prepared = await self.prepare(event)
        await self.persist(event, session, prepared)

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
    page: GamesPageListed,
    listed: ListedGame,
    details: GameDetails,
    cover_url: str | None,
) -> None:
    payload = GameCataloged(
        run_id=page.run_id,
        process_date=page.process_date,
        metacritic_slug=listed.metacritic_slug,
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
        subject=listed.metacritic_slug,
        data=payload,
        stage=settings.catalog.stage_name,
        run_id=page.run_id,
        traceparent=new_traceparent(),
    )
    await OutboxRepository(session).insert(
        OutboxInsert(
            producer=_WORKER_TYPE,
            idempotency_key=event.idempotencykey,
            topic=settings.event_name(settings.catalog.publish_event),
            partition_key=listed.metacritic_slug,
            payload=cloud_event_to_dict(event),
        )
    )
