from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.adapters.media.port import CoverStorage
from games_intel.adapters.media.storage import create_cover_storage
from games_intel.adapters.metacritic.factory import create_metacritic_port
from games_intel.adapters.metacritic.port import MetacriticPort
from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.ready import wait_until_backend_ready
from games_intel.kafka.relay import OutboxRelay
from games_intel.settings import Settings, load_settings
from games_intel.workers.catalog.handler import CatalogHandler

logger = logging.getLogger("games_intel.workers.catalog")

_WORKER_TYPE = "catalog"
SleepFn = Callable[[float], Awaitable[None]]


class CatalogRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        port: MetacriticPort,
        covers: CoverStorage,
        handler: CatalogHandler | None = None,
        sleep: SleepFn | None = None,
        consumer: KafkaConsumer | None = None,
        producer: KafkaProducer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.engine = engine
        self.port = port
        self.covers = covers
        self.handler = handler or CatalogHandler(settings, port, covers)
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        instance_id = settings.catalog.instance_id
        group_id = settings.consumer_group_id(settings.catalog.consumer_group)
        topic = settings.event_name(settings.catalog.subscribe_event)
        self.producer = producer or KafkaProducer(
            settings, worker_type=_WORKER_TYPE, instance_id=instance_id
        )
        self.consumer = consumer or KafkaConsumer(
            settings,
            worker_type=_WORKER_TYPE,
            instance_id=instance_id,
            group_id=group_id,
            topics=(topic,),
        )
        self.daemon = DaemonLoop(
            settings,
            DaemonConfig(
                worker_type=_WORKER_TYPE,
                instance_id=instance_id,
                stage_name=settings.catalog.stage_name,
                subscribe_event_key=settings.catalog.subscribe_event,
                heartbeat_interval_seconds=settings.catalog.heartbeat_interval_seconds,
                lease_seconds=settings.catalog.lease_seconds,
            ),
            consumer=self.consumer,
            producer=self.producer,
            session_factory=session_factory,
            handler=self.handler,
            sleep=self._sleep,
        )
        self.relay = OutboxRelay(session_factory, self.producer, worker_type=_WORKER_TYPE)

    async def ready(self) -> bool:
        return await is_database_ready(self.engine)

    async def run(self, stop: asyncio.Event) -> None:
        if not await wait_until_backend_ready(
            self.engine,
            self.settings,
            sleep=self._sleep,
            require_kafka=isinstance(self.producer, KafkaProducer),
        ):
            logger.error("catalog not ready: database or kafka unavailable")
            msg = "catalog not ready: database or kafka unavailable"
            raise RuntimeError(msg)
        await self.producer.start()
        try:
            await asyncio.gather(self.daemon.run(stop), self._relay_loop(stop))
        finally:
            await self.producer.stop()
            close = getattr(self.port, "aclose", None)
            if close is not None:
                await close()

    async def _relay_loop(self, stop: asyncio.Event) -> None:
        await self.relay.run_loop(stop, self._sleep)


def build_runtime(
    settings: Settings | None = None,
    *,
    port: MetacriticPort | None = None,
    covers: CoverStorage | None = None,
) -> CatalogRuntime:
    loaded = settings if settings is not None else load_settings()
    engine = create_engine(loaded)
    session_factory = create_session_factory(engine)
    resolved_port = port if port is not None else create_metacritic_port(loaded)
    resolved_covers = covers if covers is not None else create_cover_storage(loaded)
    return CatalogRuntime(
        loaded,
        session_factory=session_factory,
        engine=engine,
        port=resolved_port,
        covers=resolved_covers,
    )
