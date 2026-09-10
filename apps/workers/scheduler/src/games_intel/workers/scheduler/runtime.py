from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.runtime import SleepFn, WorkerStack, build_worker_stack, run_worker_stack
from games_intel.settings import Settings, load_settings
from games_intel.workers.scheduler.cron import CronMinuteGate
from games_intel.workers.scheduler.handler import SchedulerHandler
from games_intel.workers.scheduler.recompute import enqueue_full_recompute
from games_intel.workers.scheduler.ticks import enqueue_schedule_tick

logger = logging.getLogger("games_intel.workers.scheduler")

_WORKER_TYPE = "scheduler"
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
        stack = build_worker_stack(
            settings,
            DaemonConfig(
                worker_type=_WORKER_TYPE,
                instance_id=settings.scheduler.instance_id,
                stage_name=settings.scheduler.stage_name,
                subscribe_event_key=settings.scheduler.subscribe_event,
                heartbeat_interval_seconds=settings.scheduler.heartbeat_interval_seconds,
            ),
            session_factory=session_factory,
            handler=self.handler,
            group_id=settings.consumer_group_id(settings.scheduler.consumer_group),
            topics=(settings.event_name(settings.scheduler.subscribe_event),),
            sleep=self._sleep,
            consumer=consumer,
            producer=producer,
        )
        self._stack: WorkerStack = stack
        self.producer = stack.producer
        self.consumer = stack.consumer
        self.daemon = stack.daemon
        self.relay = stack.relay
        self._tick_gate = CronMinuteGate()
        self._recompute_gate = CronMinuteGate()

    async def ready(self) -> bool:
        return await is_database_ready(self.engine)

    async def run(self, stop: asyncio.Event) -> None:
        extra = [self._recompute_loop(stop)]
        if self.settings.scheduler.tick_source == "in_process":
            extra.append(self._tick_loop(stop))
        await run_worker_stack(
            name="scheduler",
            engine=self.engine,
            settings=self.settings,
            stack=self._stack,
            sleep=self._sleep,
            stop=stop,
            extra_coros=extra,
        )

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
