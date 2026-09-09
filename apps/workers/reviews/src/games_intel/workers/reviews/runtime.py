from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.adapters.metacritic.factory import create_metacritic_port
from games_intel.adapters.metacritic.port import MetacriticPort
from games_intel.agents.review_summarizer import (
    ReviewSummarizerAgent,
    create_review_summarizer_agent,
)
from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.ready import wait_until_backend_ready
from games_intel.kafka.relay import OutboxRelay
from games_intel.settings import Settings, load_settings
from games_intel.workers.reviews.handler import ReviewsHandler

logger = logging.getLogger("games_intel.workers.reviews")

_WORKER_TYPE = "reviews"
SleepFn = Callable[[float], Awaitable[None]]


class ReviewsRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        port: MetacriticPort,
        agent: ReviewSummarizerAgent,
        handler: ReviewsHandler | None = None,
        sleep: SleepFn | None = None,
        consumer: KafkaConsumer | None = None,
        producer: KafkaProducer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.engine = engine
        self.port = port
        self.agent = agent
        self.handler = handler or ReviewsHandler(settings, port, agent)
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        instance_id = settings.reviews.instance_id
        group_id = settings.consumer_group_id(settings.reviews.consumer_group)
        topic = settings.event_name(settings.reviews.subscribe_event)
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
                stage_name=settings.reviews.stage_name,
                subscribe_event_key=settings.reviews.subscribe_event,
                heartbeat_interval_seconds=settings.reviews.heartbeat_interval_seconds,
                lease_seconds=settings.reviews.lease_seconds,
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
            logger.error("reviews not ready: database or kafka unavailable")
            msg = "reviews not ready: database or kafka unavailable"
            raise RuntimeError(msg)
        await self.producer.start()
        try:
            await asyncio.gather(self.daemon.run(stop), self._relay_loop(stop))
        finally:
            await self.producer.stop()
            close = getattr(self.port, "aclose", None)
            if close is not None:
                await close()
            agent_close = getattr(self.agent, "aclose", None)
            if agent_close is not None:
                await agent_close()

    async def _relay_loop(self, stop: asyncio.Event) -> None:
        await self.relay.run_loop(stop, self._sleep)


def build_runtime(
    settings: Settings | None = None,
    *,
    port: MetacriticPort | None = None,
    agent: ReviewSummarizerAgent | None = None,
) -> ReviewsRuntime:
    loaded = settings if settings is not None else load_settings()
    engine = create_engine(loaded)
    session_factory = create_session_factory(engine)
    resolved_port = port if port is not None else create_metacritic_port(loaded)
    resolved_agent = agent if agent is not None else create_review_summarizer_agent(loaded)
    return ReviewsRuntime(
        loaded,
        session_factory=session_factory,
        engine=engine,
        port=resolved_port,
        agent=resolved_agent,
    )
