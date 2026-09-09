from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.ready import wait_until_backend_ready
from games_intel.kafka.relay import OutboxRelay
from games_intel.kafka.types import MessageProducer
from games_intel.settings import Settings, load_settings
from games_intel.workers.scheduler.cron import CronMinuteGate
from games_intel.workers.scheduler.ticks import enqueue_schedule_tick

logger = logging.getLogger("games_intel.workers.scheduler.tick")

_WORKER_TYPE = "scheduler"
SleepFn = Callable[[float], Awaitable[None]]
Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ExternalTickRuntime:
    """Single cron process that emits schedule_tick when tick_source=external."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        sleep: SleepFn | None = None,
        clock: Clock | None = None,
        producer: MessageProducer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.engine = engine
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        self._clock: Clock = clock if clock is not None else _utcnow
        instance_id = settings.scheduler.instance_id
        self.producer = producer or KafkaProducer(
            settings, worker_type=_WORKER_TYPE, instance_id=instance_id
        )
        self.relay = OutboxRelay(session_factory, self.producer, worker_type=_WORKER_TYPE)
        self.ticks_enqueued = 0
        self._tick_gate = CronMinuteGate()

    async def ready(self) -> bool:
        return await is_database_ready(self.engine)

    async def run(self, stop: asyncio.Event) -> None:
        if self.settings.scheduler.tick_source != "external":
            logger.error(
                "external tick container requires scheduler.tick_source=external",
            )
            msg = "scheduler.tick_source must be external for the cron container"
            raise RuntimeError(msg)
        if not await wait_until_backend_ready(
            self.engine,
            self.settings,
            sleep=self._sleep,
            require_kafka=isinstance(self.producer, KafkaProducer),
        ):
            logger.error("tick cron not ready: database or kafka unavailable")
            msg = "tick cron not ready: database or kafka unavailable"
            raise RuntimeError(msg)
        await self.producer.start()
        try:
            while not stop.is_set():
                now = self._clock()
                if self._tick_due(now):
                    async with self.session_factory() as session:
                        async with session.begin():
                            await enqueue_schedule_tick(
                                session, self.settings, trigger="cron", when=now
                            )
                    self.ticks_enqueued += 1
                    try:
                        await self.relay.publish_once()
                    except Exception as exc:
                        logger.warning(
                            "tick outbox relay failed error_type=%s",
                            type(exc).__name__,
                        )
                await self._sleep(self._sleep_seconds())
        finally:
            await self.producer.stop()

    def _tick_due(self, now: datetime) -> bool:
        scheduler = self.settings.scheduler
        if scheduler.tick_use_interval:
            return True
        return self._tick_gate.due(scheduler.tick_cron, now)

    def _sleep_seconds(self) -> float:
        scheduler = self.settings.scheduler
        if scheduler.tick_use_interval:
            return float(scheduler.tick_interval_seconds)
        return 1.0


def build_tick_runtime(settings: Settings | None = None) -> ExternalTickRuntime:
    loaded = settings if settings is not None else load_settings()
    engine = create_engine(loaded)
    session_factory = create_session_factory(engine)
    return ExternalTickRuntime(loaded, session_factory=session_factory, engine=engine)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    runtime = build_tick_runtime()
    stop = asyncio.Event()
    asyncio.run(runtime.run(stop))


if __name__ == "__main__":
    main()
