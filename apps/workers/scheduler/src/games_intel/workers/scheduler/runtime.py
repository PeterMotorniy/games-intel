from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.ready import wait_until_backend_ready
from games_intel.kafka.relay import OutboxRelay
from games_intel.settings import Settings, load_settings
from games_intel.workers.scheduler.cron import CronMinuteGate
from games_intel.workers.scheduler.handler import SchedulerHandler
from games_intel.workers.scheduler.recompute import enqueue_full_recompute
from games_intel.workers.scheduler.ticks import enqueue_schedule_tick

logger = logging.getLogger("games_intel.workers.scheduler")

_WORKER_TYPE = "scheduler"
SleepFn = Callable[[float], Awaitable[None]]
Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SchedulerRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        handler: SchedulerHandler | None = None,
        sleep: SleepFn | None = None,
        clock: Clock | None = None,
        consumer: KafkaConsumer | None = None,
        producer: KafkaProducer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.engine = engine
        self.handler = handler or SchedulerHandler(settings)
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        self._clock: Clock = clock if clock is not None else _utcnow
        instance_id = settings.scheduler.instance_id
        group_id = settings.consumer_group_id(settings.scheduler.consumer_group)
        topic = settings.event_name(settings.scheduler.subscribe_event)
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
                stage_name=settings.scheduler.stage_name,
                subscribe_event_key=settings.scheduler.subscribe_event,
                heartbeat_interval_seconds=settings.scheduler.heartbeat_interval_seconds,
            ),
            consumer=self.consumer,
            producer=self.producer,
            session_factory=session_factory,
            handler=self.handler,
            sleep=self._sleep,
        )
        self.relay = OutboxRelay(session_factory, self.producer, worker_type=_WORKER_TYPE)
        self._tick_gate = CronMinuteGate()
        self._recompute_gate = CronMinuteGate()

    async def ready(self) -> bool:
        return await is_database_ready(self.engine)

    async def run(self, stop: asyncio.Event) -> None:
        if not await wait_until_backend_ready(
            self.engine,
            self.settings,
            sleep=self._sleep,
            require_kafka=isinstance(self.producer, KafkaProducer),
        ):
            logger.error("scheduler not ready: database or kafka unavailable")
            msg = "scheduler not ready: database or kafka unavailable"
            raise RuntimeError(msg)
        await self.producer.start()
        tasks = [
            asyncio.create_task(self.daemon.run(stop), name="scheduler-daemon"),
            asyncio.create_task(self._relay_loop(stop), name="scheduler-relay"),
            asyncio.create_task(self._recompute_loop(stop), name="scheduler-recompute"),
        ]
        if self.settings.scheduler.tick_source == "in_process":
            tasks.append(asyncio.create_task(self._tick_loop(stop), name="scheduler-ticks"))
        try:
            await asyncio.gather(*tasks)
        finally:
            await self.producer.stop()

    async def _relay_loop(self, stop: asyncio.Event) -> None:
        await self.relay.run_loop(stop, self._sleep)

    async def _tick_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            now = self._clock()
            if self._tick_due(now):
                try:
                    async with self.session_factory() as session:
                        async with session.begin():
                            await enqueue_schedule_tick(
                                session, self.settings, trigger="cron", when=now
                            )
                except Exception:
                    logger.exception("scheduler tick enqueue failed")
            await self._sleep(self._tick_sleep_seconds())

    async def _recompute_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            now = self._clock()
            if self._recompute_gate.due(self.settings.similarity.full_recompute_cron, now):
                try:
                    async with self.session_factory() as session:
                        async with session.begin():
                            await enqueue_full_recompute(session, self.settings, when=now)
                except Exception:
                    logger.exception("scheduler recompute enqueue failed")
            await self._sleep(1.0)

    def _tick_due(self, now: datetime) -> bool:
        scheduler = self.settings.scheduler
        if scheduler.tick_use_interval:
            return True
        return self._tick_gate.due(scheduler.tick_cron, now)

    def _tick_sleep_seconds(self) -> float:
        scheduler = self.settings.scheduler
        if scheduler.tick_use_interval:
            return float(scheduler.tick_interval_seconds)
        return 1.0


def build_runtime(settings: Settings | None = None) -> SchedulerRuntime:
    loaded = settings if settings is not None else load_settings()
    engine = create_engine(loaded)
    session_factory = create_session_factory(engine)
    return SchedulerRuntime(loaded, session_factory=session_factory, engine=engine)
