from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.port import MetacriticPort
from games_intel.contracts.adapters import (
    AdapterError,
    CanaryParseInput,
    GameListing,
    ListBrowsePageInput,
    ListNewReleasesInput,
)
from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.ids import new_traceparent
from games_intel.contracts.payloads import GamesPageListed, ListedGame, RunRequested
from games_intel.db.records import OutboxInsert
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import (
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionStage,
    InsertOutcome,
)
from games_intel.kafka.classify import map_adapter_error
from games_intel.kafka.exceptions import ParseError
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings

_WORKER_TYPE = "discovery"


@dataclass(frozen=True, slots=True)
class _DiscoveryPrepared:
    requested: RunRequested
    listing: GameListing


class DiscoveryHandler:
    """Listing via MetacriticPort only. Does not know CatalogWorker."""

    def __init__(self, settings: Settings, port: MetacriticPort) -> None:
        self.settings = settings
        self.port = port

    async def prepare(self, event: CloudEvent[Any]) -> _DiscoveryPrepared:
        requested = event.data
        if not isinstance(requested, RunRequested):
            msg = "discovery expected RunRequested payload"
            raise TypeError(msg)
        listing = await self._fetch_listing(requested)
        return _DiscoveryPrepared(requested=requested, listing=listing)

    async def persist(
        self, event: CloudEvent[Any], session: AsyncSession, prepared: _DiscoveryPrepared
    ) -> None:
        await self._persist_success(event, session, prepared.requested, prepared.listing)

    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None:
        prepared = await self.prepare(event)
        await self.persist(event, session, prepared)

    async def on_terminal_failure(
        self,
        event: CloudEvent[Any],
        session: AsyncSession,
        exc: BaseException,
    ) -> None:
        del exc
        requested = event.data
        if not isinstance(requested, RunRequested):
            return
        await IngestionRepository(session).update_run(
            requested.run_id,
            status=IngestionRunStatus.failed,
            completed_at=datetime.now(UTC),
        )

    async def _fetch_listing(self, requested: RunRequested) -> GameListing:
        metacritic = self.settings.adapters.metacritic
        if metacritic.canary_enabled:
            await self._run_canary(metacritic.canary_slug)
        limit = requested.limit or self.settings.discovery.list_limit
        try:
            if requested.source == self.settings.scheduler.new_releases_source:
                return await self.port.list_new_releases(ListNewReleasesInput(limit=limit))
            page = requested.page if requested.page is not None else 1
            return await self.port.list_browse_page(
                ListBrowsePageInput(page=page, limit=self.settings.discovery.browse_list_limit)
            )
        except MetacriticAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc

    async def _run_canary(self, slug: str) -> None:
        try:
            result = await self.port.canary_parse(CanaryParseInput(slug=slug))
        except MetacriticAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc
        if result.ok:
            return
        code = result.error_code or "parse_error"
        if code == "parse_error":
            raise ParseError("canary parse failed")
        raise map_adapter_error(AdapterError(code=code, message="canary parse failed"))

    async def _persist_success(
        self,
        event: CloudEvent[Any],
        session: AsyncSession,
        requested: RunRequested,
        listing: GameListing,
    ) -> None:
        ingestion = IngestionRepository(session)
        catalog = GameCatalogRepository(session)
        seen = set(await ingestion.list_daily_processed_slugs(requested.process_date))
        discovered = [item for item in listing.items if item.slug not in seen]
        await ingestion.update_run(
            requested.run_id,
            status=IngestionRunStatus.running,
        )
        listed: list[ListedGame] = []
        for item in discovered:
            game_id, _outcome = await catalog.ensure_game_stub(
                metacritic_slug=item.slug,
                title=item.title,
                listing_url=str(item.listing_url),
            )
            slug_outcome = await ingestion.record_daily_processed_slug(
                requested.process_date, item.slug
            )
            if slug_outcome is InsertOutcome.duplicate:
                continue
            await ingestion.upsert_item(
                run_id=requested.run_id,
                metacritic_slug=item.slug,
                process_date=requested.process_date,
                stage=IngestionStage.discovered,
                status=IngestionItemStatus.completed,
                game_id=game_id,
                event_id=event.id,
            )
            listed.append(
                ListedGame(
                    metacritic_slug=item.slug,
                    title=item.title,
                    listing_url=item.listing_url,
                    position=item.position,
                )
            )
        if listed:
            await _enqueue_page_listed(
                session,
                self.settings,
                requested=requested,
                games=listed,
            )
        published = len(listed)
        await _advance_cursor(ingestion, requested, self.settings)
        await ingestion.update_run(
            requested.run_id,
            status=IngestionRunStatus.completed,
            discovered_count=published,
            completed_at=datetime.now(UTC),
        )


async def _advance_cursor(
    ingestion: IngestionRepository,
    requested: RunRequested,
    settings: Settings,
) -> None:
    cursor = await ingestion.get_cursor(requested.process_date)
    if requested.source == settings.scheduler.new_releases_source:
        last_browse = cursor.last_browse_page if cursor is not None else None
        await ingestion.advance_cursor(
            requested.process_date,
            new_releases_done=True,
            last_browse_page=last_browse,
        )
        return
    page = requested.page if requested.page is not None else 1
    await ingestion.advance_cursor(
        requested.process_date,
        new_releases_done=True,
        last_browse_page=page,
    )


async def _enqueue_page_listed(
    session: AsyncSession,
    settings: Settings,
    *,
    requested: RunRequested,
    games: list[ListedGame],
) -> None:
    payload = GamesPageListed(
        run_id=requested.run_id,
        process_date=requested.process_date,
        source=requested.source,
        page=requested.page,
        games=games,
    )
    event = build_cloud_event(
        settings,
        settings.discovery.publish_event,
        source=worker_source(settings, _WORKER_TYPE),
        subject=str(requested.run_id),
        data=payload,
        stage=settings.discovery.stage_name,
        run_id=requested.run_id,
        traceparent=new_traceparent(),
    )
    await OutboxRepository(session).insert(
        OutboxInsert(
            producer=_WORKER_TYPE,
            idempotency_key=event.idempotencykey,
            topic=settings.event_name(settings.discovery.publish_event),
            partition_key=str(requested.run_id),
            payload=cloud_event_to_dict(event),
        )
    )
