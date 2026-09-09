from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from games_intel.adapters.media.port import CoverStorage
from games_intel.adapters.media.storage import create_cover_storage
from games_intel.api.errors import (
    ProblemError,
    http_exception_handler,
    problem_error_handler,
    validation_error_handler,
)
from games_intel.api.routers import create_catalog_router, create_media_router
from games_intel.api.routers_health import create_health_router
from games_intel.api.routers_monitor import create_monitor_router
from games_intel.api.schemas import ProblemDetails
from games_intel.api.services import (
    CatalogQueryService,
    CoverQueryService,
    HealthService,
    MonitorQueryService,
    RunCommandService,
)
from games_intel.db.engine import create_engine, create_session_factory
from games_intel.kafka.types import MessageProducer
from games_intel.settings import Settings, default_instance_id, load_settings

logger = logging.getLogger("games_intel.api")

ReadyFn = Callable[[], Awaitable[bool]]
Clock = Callable[[], datetime]
_API_PRODUCER = "api"


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    covers: CoverStorage | None = None,
    postgres_ready: ReadyFn | None = None,
    kafka_ready: ReadyFn | None = None,
    clock: Clock | None = None,
    outbox_producer: MessageProducer | None = None,
    enable_outbox_relay: bool = False,
) -> FastAPI:
    loaded = settings if settings is not None else load_settings()
    resolved_kafka_ready = kafka_ready
    if resolved_kafka_ready is None and enable_outbox_relay:

        async def _probe_kafka() -> bool:
            from games_intel.kafka.ready import is_kafka_ready

            return await is_kafka_ready(loaded)

        resolved_kafka_ready = _probe_kafka

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned_engine: AsyncEngine | None = None
        runtime_engine = engine
        runtime_sessions = session_factory
        if runtime_sessions is None and runtime_engine is None:
            database_url = loaded.database.url.get_secret_value()
            if database_url:
                owned_engine = create_engine(loaded)
                runtime_engine = owned_engine
                runtime_sessions = create_session_factory(owned_engine)
        cover_storage = covers if covers is not None else create_cover_storage(loaded)
        _bind_state(
            app,
            loaded,
            engine=runtime_engine,
            session_factory=runtime_sessions,
            covers=cover_storage,
            postgres_ready=postgres_ready,
            kafka_ready=resolved_kafka_ready,
            clock=clock,
        )
        stop = asyncio.Event()
        relay_task: asyncio.Task[None] | None = None
        producer = outbox_producer
        owned_producer = False
        if enable_outbox_relay and runtime_sessions is not None:
            relay_task, producer, owned_producer = await _start_outbox_relay(
                loaded, runtime_sessions, producer, stop
            )
        try:
            yield
        finally:
            stop.set()
            if relay_task is not None:
                relay_task.cancel()
                try:
                    await relay_task
                except asyncio.CancelledError:
                    pass
            if owned_producer and producer is not None:
                await producer.stop()
            if owned_engine is not None:
                await owned_engine.dispose()

    app = FastAPI(
        title="games-intel-api",
        version="0.1.0",
        lifespan=lifespan,
        responses={
            400: {"model": ProblemDetails},
            404: {"model": ProblemDetails},
            503: {"model": ProblemDetails},
        },
    )
    app.state.settings = loaded
    cover_storage = covers if covers is not None else create_cover_storage(loaded)
    _bind_state(
        app,
        loaded,
        engine=engine,
        session_factory=session_factory,
        covers=cover_storage,
        postgres_ready=postgres_ready,
        kafka_ready=resolved_kafka_ready,
        clock=clock,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=loaded.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_exception_handler(ProblemError, problem_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(create_health_router())
    app.include_router(create_catalog_router(loaded))
    app.include_router(create_media_router())
    app.include_router(create_monitor_router(loaded))
    return app


def _bind_state(
    app: FastAPI,
    settings: Settings,
    *,
    engine: AsyncEngine | None,
    session_factory: async_sessionmaker[AsyncSession] | None,
    covers: CoverStorage,
    postgres_ready: ReadyFn | None,
    kafka_ready: ReadyFn | None,
    clock: Clock | None,
) -> None:
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.covers_storage = covers
    app.state.catalog = CatalogQueryService(settings, session_factory)
    app.state.covers = CoverQueryService(settings, covers)
    app.state.monitor = MonitorQueryService(settings, session_factory, clock=clock)
    app.state.runs = RunCommandService(settings, session_factory, clock=clock)
    app.state.health = HealthService(
        engine,
        postgres_ready=postgres_ready,
        kafka_ready=kafka_ready,
    )


async def _start_outbox_relay(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    producer: MessageProducer | None,
    stop: asyncio.Event,
) -> tuple[asyncio.Task[None] | None, MessageProducer | None, bool]:
    from games_intel.kafka.producer import KafkaProducer
    from games_intel.kafka.relay import OutboxRelay

    owned = False
    runtime = producer
    if runtime is None:
        runtime = KafkaProducer(
            settings,
            worker_type=_API_PRODUCER,
            instance_id=default_instance_id(),
        )
        owned = True
    try:
        await runtime.start()
    except Exception:
        logger.warning(
            "api outbox relay producer failed to start error_type=startup",
            exc_info=True,
        )
        return None, runtime if owned else producer, owned
    relay = OutboxRelay(session_factory, runtime, worker_type=_API_PRODUCER)

    async def _loop() -> None:
        await relay.run_loop(stop, asyncio.sleep)

    return asyncio.create_task(_loop(), name="api-outbox-relay"), runtime, owned


def openapi_schema(settings: Settings | None = None) -> dict[str, object]:
    return create_app(settings or Settings()).openapi()
