from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.adapters.stt.factory import create_stt_port
from games_intel.adapters.stt.port import SttPort
from games_intel.adapters.youtube.factory import create_youtube_port
from games_intel.adapters.youtube.port import YouTubePort
from games_intel.agents.letsplay_analyst import (
    LetsPlayAnalystAgent,
    create_letsplay_analyst_agent,
)
from games_intel.agents.transcription import TranscriptionAgent, create_transcription_agent
from games_intel.db.engine import create_engine, create_session_factory, is_database_ready
from games_intel.kafka.consumer import KafkaConsumer
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.producer import KafkaProducer
from games_intel.kafka.ready import wait_until_backend_ready
from games_intel.kafka.relay import OutboxRelay
from games_intel.settings import Settings, load_settings
from games_intel.workers.letsplay.handler import LetsPlayHandler

logger = logging.getLogger("games_intel.workers.letsplay")

_WORKER_TYPE = "letsplay"
SleepFn = Callable[[float], Awaitable[None]]


class LetsPlayRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
        youtube: YouTubePort,
        transcription: TranscriptionAgent,
        analyst: LetsPlayAnalystAgent,
        stt: SttPort | None = None,
        handler: LetsPlayHandler | None = None,
        sleep: SleepFn | None = None,
        consumer: KafkaConsumer | None = None,
        producer: KafkaProducer | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.engine = engine
        self.youtube = youtube
        self.transcription = transcription
        self.analyst = analyst
        self.stt = stt
        self.handler = handler or LetsPlayHandler(settings, youtube, transcription, analyst)
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        instance_id = settings.letsplay.instance_id
        group_id = settings.consumer_group_id(settings.letsplay.consumer_group)
        topic = settings.event_name(settings.letsplay.subscribe_event)
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
                stage_name=settings.letsplay.stage_name,
                subscribe_event_key=settings.letsplay.subscribe_event,
                heartbeat_interval_seconds=settings.letsplay.heartbeat_interval_seconds,
                lease_seconds=settings.letsplay.lease_seconds,
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
            logger.error("letsplay not ready: database or kafka unavailable")
            msg = "letsplay not ready: database or kafka unavailable"
            raise RuntimeError(msg)
        await self.producer.start()
        try:
            await asyncio.gather(self.daemon.run(stop), self._relay_loop(stop))
        finally:
            await self.producer.stop()
            close = getattr(self.youtube, "aclose", None)
            if close is not None:
                await close()
            transcription_close = getattr(self.transcription, "aclose", None)
            if transcription_close is not None:
                await transcription_close()
            analyst_close = getattr(self.analyst, "aclose", None)
            if analyst_close is not None:
                await analyst_close()

    async def _relay_loop(self, stop: asyncio.Event) -> None:
        await self.relay.run_loop(stop, self._sleep)


def build_runtime(
    settings: Settings | None = None,
    *,
    youtube: YouTubePort | None = None,
    transcription: TranscriptionAgent | None = None,
    analyst: LetsPlayAnalystAgent | None = None,
) -> LetsPlayRuntime:
    loaded = settings if settings is not None else load_settings()
    engine = create_engine(loaded)
    session_factory = create_session_factory(engine)
    resolved_youtube = youtube if youtube is not None else create_youtube_port(loaded)
    resolved_transcription = (
        transcription
        if transcription is not None
        else create_transcription_agent(loaded, port=create_stt_port(loaded))
    )
    resolved_analyst = analyst if analyst is not None else create_letsplay_analyst_agent(loaded)
    return LetsPlayRuntime(
        loaded,
        session_factory=session_factory,
        engine=engine,
        youtube=resolved_youtube,
        transcription=resolved_transcription,
        analyst=resolved_analyst,
    )
