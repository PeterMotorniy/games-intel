from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.adapters.media.images import cover_media_type
from games_intel.adapters.media.port import CoverStorage
from games_intel.api.errors import DatabaseUnavailableError, ProblemError
from games_intel.api.mapping import (
    game_card,
    game_list_response,
    monitor_snapshot,
    parse_order,
    parse_sort,
)
from games_intel.api.schemas import (
    GameCardRead,
    GameListResponse,
    MonitorSnapshot,
    PlatformListResponse,
    RunAcceptedResponse,
)
from games_intel.contracts.builder import build_cloud_event, format_idempotency_key
from games_intel.contracts.ids import new_event_id
from games_intel.contracts.payloads import ScheduleTick
from games_intel.db.engine import is_database_ready
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.similar import SimilarGamesRepository
from games_intel.kafka.source import api_source
from games_intel.settings import Settings, process_date_for

logger = logging.getLogger("games_intel.api")

T = TypeVar("T")
ReadyFn = Callable[[], Awaitable[bool]]
Clock = Callable[[], datetime]

_API_PRODUCER = "api"
_TICK_STAGE = "tick"


def _looks_like_db_down(exc: BaseException) -> bool:
    if isinstance(
        exc, OperationalError | InterfaceError | ConnectionError | TimeoutError | OSError
    ):
        return True
    return type(exc).__name__ in {"UndefinedTableError", "CannotConnectNowError"}


class CatalogQueryService:
    """Read-only catalog: routers call this, SQL stays in repositories."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession] | None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory

    async def list_games(
        self,
        *,
        q: str | None,
        platform: str | None,
        sort: str,
        order: str,
        page: int,
        page_size: int,
    ) -> GameListResponse:
        query = q.strip() if q else None
        platform_code = platform.strip() if platform else None

        async def _load(session: AsyncSession) -> GameListResponse:
            page_data = await GameCatalogRepository(session).list_games(
                q=query or None,
                platform=platform_code or None,
                sort=parse_sort(sort),
                order=parse_order(order),
                page=page,
                page_size=page_size,
            )
            return game_list_response(page_data)

        return await self._with_session(_load)

    async def get_game(self, slug: str) -> GameCardRead:
        async def _load(session: AsyncSession) -> GameCardRead:
            catalog = GameCatalogRepository(session)
            game = await catalog.get_by_slug(slug)
            if game is None:
                raise ProblemError(404, "Not Found", f"game not found: {slug}")
            similar = await SimilarGamesRepository(session).list_for_slug(slug)
            return game_card(game, similar)

        return await self._with_session(_load)

    async def list_platforms(self) -> PlatformListResponse:
        async def _load(session: AsyncSession) -> PlatformListResponse:
            codes = await GameCatalogRepository(session).list_platform_codes()
            return PlatformListResponse(items=list(codes))

        return await self._with_session(_load)

    async def _with_session(self, fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
        factory = self._session_factory
        if factory is None:
            raise DatabaseUnavailableError
        try:
            async with factory() as session:
                return await fn(session)
        except ProblemError:
            raise
        except DatabaseUnavailableError:
            raise
        except Exception as exc:
            if _looks_like_db_down(exc):
                logger.warning("database unavailable error_type=%s", type(exc).__name__)
                raise DatabaseUnavailableError from exc
            raise


class MonitorQueryService:
    """Read-only pipeline snapshot from Postgres. UI never talks to Kafka."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession] | None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._clock: Clock = clock if clock is not None else (lambda: datetime.now(UTC))

    async def snapshot(self) -> MonitorSnapshot:
        now = self._clock()
        process_date = process_date_for(self._settings, now)

        async def _load(session: AsyncSession) -> MonitorSnapshot:
            aggregates = await IngestionRepository(session).monitor_aggregates(process_date)
            return monitor_snapshot(
                aggregates,
                process_date=process_date,
                stale_after_seconds=self._settings.monitor.heartbeat_stale_seconds,
                now=now,
                include_circuit=self._settings.monitor.include_scrape_circuit_state,
                include_last_parse_error=self._settings.monitor.include_last_parse_error,
                show_instance_id=self._settings.monitor.show_instance_id,
            )

        return await self._with_session(_load)

    async def _with_session(self, fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
        factory = self._session_factory
        if factory is None:
            raise DatabaseUnavailableError
        try:
            async with factory() as session:
                return await fn(session)
        except ProblemError:
            raise
        except DatabaseUnavailableError:
            raise
        except Exception as exc:
            if _looks_like_db_down(exc):
                logger.warning("database unavailable error_type=%s", type(exc).__name__)
                raise DatabaseUnavailableError from exc
            raise


class RunCommandService:
    """Enqueue a manual schedule tick. Does not wait for workers."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession] | None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._clock: Clock = clock if clock is not None else (lambda: datetime.now(UTC))

    async def accept_manual_run(self) -> RunAcceptedResponse:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            now = now.replace(tzinfo=UTC)
        process_date = process_date_for(self._settings, now)
        event_key = self._settings.scheduler.subscribe_event
        event_type = self._settings.event_name(event_key)
        event_id = new_event_id()
        tick = ScheduleTick(trigger="manual", requested_at=now, process_date=process_date)
        event = build_cloud_event(
            self._settings,
            event_key,
            source=api_source(self._settings),
            subject=process_date.isoformat(),
            data=tick,
            stage=_TICK_STAGE,
            event_id=event_id,
            occurred_at=now,
            idempotency_key=format_idempotency_key(
                self._settings.idempotency.key_template,
                event_type=event_type,
                run_id=event_id,
                subject=process_date.isoformat(),
                stage=_TICK_STAGE,
            ),
        )

        async def _write(session: AsyncSession) -> RunAcceptedResponse:
            await OutboxRepository(session).insert_schedule_tick(
                producer=_API_PRODUCER,
                idempotency_key=event.idempotencykey,
                topic=event_type,
                partition_key=process_date.isoformat(),
                payload=event.model_dump(mode="json"),
            )
            return RunAcceptedResponse(status="run_accepted", process_date=process_date)

        return await self._with_session(_write)

    async def _with_session(self, fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
        factory = self._session_factory
        if factory is None:
            raise DatabaseUnavailableError
        try:
            async with factory() as session:
                async with session.begin():
                    return await fn(session)
        except ProblemError:
            raise
        except DatabaseUnavailableError:
            raise
        except Exception as exc:
            if _looks_like_db_down(exc):
                logger.warning("database unavailable error_type=%s", type(exc).__name__)
                raise DatabaseUnavailableError from exc
            raise


class CoverQueryService:
    def __init__(self, settings: Settings, covers: CoverStorage) -> None:
        self._settings = settings
        self._covers = covers

    async def load(self, slug: str) -> tuple[bytes, str, str]:
        data = await self._covers.load(slug)
        if data is None:
            raise ProblemError(404, "Not Found", f"cover not found: {slug}")
        media_type = cover_media_type(data) or "application/octet-stream"
        return data, media_type, self._settings.media.covers_cache_control


class HealthService:
    def __init__(
        self,
        engine: AsyncEngine | None,
        *,
        postgres_ready: ReadyFn | None = None,
        kafka_ready: ReadyFn | None = None,
    ) -> None:
        self._engine = engine
        self._postgres_ready = postgres_ready
        self._kafka_ready = kafka_ready

    async def postgres_ok(self) -> bool:
        if self._postgres_ready is not None:
            return await self._postgres_ready()
        if self._engine is None:
            return False
        return await is_database_ready(self._engine)

    async def kafka_ok(self) -> bool | None:
        if self._kafka_ready is None:
            return None
        return await self._kafka_ready()
