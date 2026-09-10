from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.adapters.embeddings.factory import create_embedding_port
from games_intel.adapters.embeddings.port import EmbeddingPort
from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.runtime import SleepFn, WorkerStack, build_worker_stack, run_worker_stack
from games_intel.settings import Settings, load_settings
from games_intel.workers.similarity.handler import SimilarityHandler

_WORKER_TYPE = "similarity"


class SimilarityRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        embeddings: EmbeddingPort,
        handler: SimilarityHandler | None = None,
        sleep: SleepFn | None = None,
        consumer: KafkaConsumer | None = None,
        producer: KafkaProducer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.engine = engine
        self.embeddings = embeddings
        self.handler = handler or SimilarityHandler(
            settings, embeddings, session_factory=session_factory
        )
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        stack = build_worker_stack(
            settings,
            DaemonConfig(
                worker_type=_WORKER_TYPE,
                instance_id=settings.similarity.instance_id,
                stage_name=settings.similarity.stage_name,
                subscribe_event_key=settings.similarity.subscribe_event,
                extra_subscribe_event_keys=(
                    settings.similarity.subscribe_reviews_event,
                    settings.similarity.subscribe_recompute_event,
                ),
                heartbeat_interval_seconds=settings.similarity.heartbeat_interval_seconds,
                lease_seconds=settings.similarity.lease_seconds,
            ),
            session_factory=session_factory,
            handler=self.handler,
            group_id=settings.consumer_group_id(settings.similarity.consumer_group),
            topics=(
                settings.event_name(settings.similarity.subscribe_event),
                settings.event_name(settings.similarity.subscribe_reviews_event),
                settings.event_name(settings.similarity.subscribe_recompute_event),
            ),
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
            name="similarity",
            engine=self.engine,
            settings=self.settings,
            stack=self._stack,
            sleep=self._sleep,
            stop=stop,
            closeables=(self.embeddings,),
        )


def build_runtime(
    settings: Settings | None = None,
    *,
    embeddings: EmbeddingPort | None = None,
) -> SimilarityRuntime:
    loaded = settings if settings is not None else load_settings()
    engine = create_engine(loaded)
    session_factory = create_session_factory(engine)
    resolved = embeddings if embeddings is not None else create_embedding_port(loaded)
    return SimilarityRuntime(
        loaded,
        session_factory=session_factory,
        engine=engine,
        embeddings=resolved,
    )
