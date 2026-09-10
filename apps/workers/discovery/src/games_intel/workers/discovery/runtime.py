from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.adapters.metacritic.factory import create_metacritic_port
from games_intel.adapters.metacritic.port import MetacriticPort
from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.runtime import SleepFn, WorkerStack, build_worker_stack, run_worker_stack
from games_intel.settings import Settings, load_settings
from games_intel.workers.discovery.handler import DiscoveryHandler

_WORKER_TYPE = "discovery"


class DiscoveryRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        port: MetacriticPort,
        handler: DiscoveryHandler | None = None,
        sleep: SleepFn | None = None,
        consumer: KafkaConsumer | None = None,
        producer: KafkaProducer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.engine = engine
        self.port = port
        self.handler = handler or DiscoveryHandler(settings, port)
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        stack = build_worker_stack(
            settings,
            DaemonConfig(
                worker_type=_WORKER_TYPE,
                instance_id=settings.discovery.instance_id,
                stage_name=settings.discovery.stage_name,
                subscribe_event_key=settings.discovery.subscribe_event,
                heartbeat_interval_seconds=settings.discovery.heartbeat_interval_seconds,
                lease_seconds=settings.discovery.lease_seconds,
            ),
            session_factory=session_factory,
            handler=self.handler,
            group_id=settings.consumer_group_id(settings.discovery.consumer_group),
            topics=(settings.event_name(settings.discovery.subscribe_event),),
            sleep=self._sleep,
            consumer=consumer,
            producer=producer,
        )
        self._stack: WorkerStack = stack
        self.producer = stack.producer
        self.consumer = stack.consumer
        self.daemon = stack.daemon
        self.relay = stack.relay

    async def ready(self) -> bool:
        return await is_database_ready(self.engine)

    async def run(self, stop: asyncio.Event) -> None:
        await run_worker_stack(
            name="discovery",
            engine=self.engine,
            settings=self.settings,
            stack=self._stack,
            sleep=self._sleep,
            stop=stop,
            closeables=(self.port,),
        )


def build_runtime(
    settings: Settings | None = None,
    *,
    port: MetacriticPort | None = None,
) -> DiscoveryRuntime:
    loaded = settings if settings is not None else load_settings()
    engine = create_engine(loaded)
    session_factory = create_session_factory(engine)
    resolved = port if port is not None else create_metacritic_port(loaded)
    return DiscoveryRuntime(loaded, session_factory=session_factory, engine=engine, port=resolved)
