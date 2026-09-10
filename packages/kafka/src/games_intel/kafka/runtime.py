from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.db.engine import assert_embedding_dimension
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop, EventHandler
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.ready import wait_until_backend_ready
from games_intel.kafka.relay import OutboxRelay
from games_intel.kafka.types import MessageConsumer, MessageProducer
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.kafka.runtime")

SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class WorkerStack:
    producer: MessageProducer
    consumer: MessageConsumer
    daemon: DaemonLoop
    relay: OutboxRelay


async def aclose_optional(obj: object) -> None:
    close = getattr(obj, "aclose", None)
    if close is None:
        return
    await close()


def build_worker_stack(
    settings: Settings,
    config: DaemonConfig,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    handler: EventHandler,
    group_id: str,
    topics: Sequence[str],
    sleep: SleepFn,
    consumer: MessageConsumer | None = None,
    producer: MessageProducer | None = None,
) -> WorkerStack:
    resolved_producer = producer or KafkaProducer(
        settings, worker_type=config.worker_type, instance_id=config.instance_id
    )
    resolved_consumer = consumer or KafkaConsumer(
        settings,
        worker_type=config.worker_type,
        instance_id=config.instance_id,
        group_id=group_id,
        topics=tuple(topics),
    )
    daemon = DaemonLoop(
        settings,
        config,
        consumer=resolved_consumer,
        producer=resolved_producer,
        session_factory=session_factory,
        handler=handler,
        sleep=sleep,
    )
    relay = OutboxRelay(
        session_factory,
        resolved_producer,
        worker_type=config.worker_type,
        instance_id=config.instance_id,
    )
    return WorkerStack(
        producer=resolved_producer,
        consumer=resolved_consumer,
        daemon=daemon,
        relay=relay,
    )


async def run_worker_stack(
    *,
    name: str,
    engine: AsyncEngine,
    settings: Settings,
    stack: WorkerStack,
    sleep: SleepFn,
    stop: asyncio.Event,
    extra_coros: Sequence[Awaitable[None]] = (),
    closeables: Sequence[object] = (),
) -> None:
    if not await wait_until_backend_ready(
        engine,
        settings,
        sleep=sleep,
        require_kafka=isinstance(stack.producer, KafkaProducer),
    ):
        logger.error("%s not ready: database or kafka unavailable", name)
        msg = f"{name} not ready: database or kafka unavailable"
        raise RuntimeError(msg)
    await assert_embedding_dimension(engine, settings.embeddings.vector_dim)
    await stack.producer.start()
    try:
        await asyncio.gather(
            stack.daemon.run(stop),
            stack.relay.run_loop(stop, sleep),
            *extra_coros,
        )
    finally:
        await stack.producer.stop()
        for obj in closeables:
            await aclose_optional(obj)
