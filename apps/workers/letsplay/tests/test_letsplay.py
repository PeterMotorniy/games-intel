from __future__ import annotations

import ast
import asyncio
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.fake import FakeYouTubeAdapter
from games_intel.agents.letsplay_analyst.exceptions import (
    LlmStructureError as AgentLlmStructureError,
)
from games_intel.agents.transcription.exceptions import SttFailedError
from games_intel.contracts import GameCataloged, build_cloud_event
from games_intel.contracts.adapters import (
    AudioResult,
    GetAudioInput,
    LetsPlaySearch,
    SearchLetsPlaysInput,
    TranscriptResult,
    VideoHit,
)
from games_intel.contracts.agents import (
    LetsPlayAnalystInput,
    LetsPlayConclusion,
    TranscriptionInput,
    TranscriptionOutput,
)
from games_intel.contracts.envelope import CloudEvent
from games_intel.db.records import CatalogSlice, PlatformScoreRecord, ReviewsSlice
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.reviews import GameReviewsRepository
from games_intel.db.types import (
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionStage,
    LetsPlayStatus,
    RunTrigger,
)
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.serialization import encode_cloud_event
from games_intel.kafka.source import worker_source
from games_intel.kafka.testing import FakeBroker, FakeConsumer, FakeProducer
from games_intel.kafka.types import IncomingRecord
from games_intel.settings import Settings
from games_intel.workers.letsplay.handler import LetsPlayHandler, clip_transcript

PROCESS_DATE = date(2026, 9, 8)
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-0000000000ee")
SLUG = "elden-ring"
COVER_URL = "/api/v1/media/covers/elden-ring"
VIDEO_ID = "abc123xyz"
LETSPLAY_SRC = Path(__file__).resolve().parents[1] / "src" / "games_intel" / "workers" / "letsplay"
REPO_ROOT = Path(__file__).resolve().parents[4]

_ANALYST_OUTPUT = LetsPlayConclusion(
    conclusion="Блогер в восторге от мира.",
    highlights=["исследование", "боссы"],
)


class FakeTranscription:
    def __init__(
        self,
        output: TranscriptionOutput | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[TranscriptionInput] = []
        self.output = output or TranscriptionOutput(text="spoken transcript", language="en")
        self.error = error

    async def ainvoke(self, inp: TranscriptionInput) -> TranscriptionOutput:
        self.calls.append(inp)
        if self.error is not None:
            raise self.error
        return self.output


class FakeAnalyst:
    def __init__(
        self,
        output: LetsPlayConclusion | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[LetsPlayAnalystInput] = []
        self.output = output if output is not None else _ANALYST_OUTPUT
        self.error = error

    async def ainvoke(self, inp: LetsPlayAnalystInput) -> LetsPlayConclusion:
        self.calls.append(inp)
        if self.error is not None:
            raise self.error
        return self.output


def _settings(
    *, instance_id: str = "letsplay-1", stt_enabled: bool = False, **letsplay_extra: Any
) -> Settings:
    base = Settings()
    retry = base.retry.model_copy(
        update={"max_attempts": 3, "backoff_base_seconds": 0, "jitter_ratio": 0}
    )
    letsplay = base.letsplay.model_copy(
        update={"instance_id": instance_id, "stt_enabled": stt_enabled, **letsplay_extra}
    )
    return base.model_copy(update={"retry": retry, "letsplay": letsplay})


def _hit() -> VideoHit:
    return VideoHit(
        video_id=VIDEO_ID,
        title="Elden Ring Let's Play",
        view_count=1_000_000,
        duration_seconds=3600,
        channel_title="FromSoftFan",
        url=HttpUrl(f"https://www.youtube.com/watch?v={VIDEO_ID}"),
    )


def _ok_transcript(text: str = "The world is vast and the bosses are tough.") -> TranscriptResult:
    return TranscriptResult(status="ok", language="en", text=text, truncated=False)


def _discovered(
    *,
    event_id: str,
    run_id: UUID = RUN_ID,
    slug: str = SLUG,
    settings: Settings | None = None,
) -> CloudEvent[Any]:
    loaded = settings if settings is not None else Settings()
    data = GameCataloged(
        run_id=run_id,
        process_date=PROCESS_DATE,
        metacritic_slug=slug,
        title="Elden Ring",
    )
    return build_cloud_event(
        loaded,
        loaded.letsplay.subscribe_event,
        source=worker_source(loaded, "catalog"),
        subject=slug,
        data=data,
        stage="cataloged",
        run_id=run_id,
        event_id=event_id,
        occurred_at=NOW,
    )


def _record(event: CloudEvent[Any], settings: Settings, *, offset: int = 0) -> IncomingRecord:
    return IncomingRecord(
        topic=settings.event_name(settings.letsplay.subscribe_event),
        partition=0,
        offset=offset,
        key=event.subject,
        value=encode_cloud_event(event),
    )


async def _no_sleep(_delay: float) -> None:
    return None


def _see_committed(session: AsyncSession) -> None:
    session.expire_all()


async def _seed(session: AsyncSession, *, run_id: UUID = RUN_ID, slug: str = SLUG) -> None:
    ingestion = IngestionRepository(session)
    catalog = GameCatalogRepository(session)
    await ingestion.create_run(
        process_date=PROCESS_DATE,
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.cron,
        run_id=run_id,
        status=IngestionRunStatus.completed,
    )
    await catalog.upsert_catalog(
        CatalogSlice(
            metacritic_slug=slug,
            title="Elden Ring",
            listing_url=f"https://www.metacritic.com/game/{slug}/",
            cover_url=COVER_URL,
            cover_source_url="https://static.metacritic.com/images/elden-ring.jpg",
            developer="FromSoftware",
            publisher="Bandai Namco",
            genres=("Action", "RPG"),
            release_date=date(2022, 2, 25),
            description="An open-world action RPG.",
            video_url="https://www.youtube.com/watch?v=trailer",
            platforms=(PlatformScoreRecord(platform_code="ps5", metascore=96, userscore=None),),
        )
    )
    await GameReviewsRepository(session).update_reviews(
        ReviewsSlice(
            metacritic_slug=slug,
            critic_likes=("бой",),
            critic_dislikes=("баги",),
            critic_summary="Критики хвалят бой.",
            user_likes=("мир",),
            user_dislikes=(),
            user_summary="Игрокам нравится мир.",
        )
    )
    game = await catalog.get_by_slug(slug)
    assert game is not None
    await ingestion.upsert_item(
        run_id=run_id,
        metacritic_slug=slug,
        process_date=PROCESS_DATE,
        stage=IngestionStage.discovered,
        status=IngestionItemStatus.completed,
        game_id=game.id,
        event_id="discovered-seed",
    )
    await session.commit()
    session.expire_all()


def _loop(
    session_factory: async_sessionmaker[AsyncSession],
    handler: LetsPlayHandler,
    settings: Settings,
    *,
    instance_id: str = "letsplay-1",
) -> tuple[DaemonLoop, FakeBroker, FakeConsumer]:
    broker = FakeBroker()
    consumer = FakeConsumer(broker, (settings.event_name(settings.letsplay.subscribe_event),))
    producer = FakeProducer(broker)
    loop = DaemonLoop(
        settings,
        DaemonConfig(
            worker_type="letsplay",
            instance_id=instance_id,
            stage_name=settings.letsplay.stage_name,
            subscribe_event_key=settings.letsplay.subscribe_event,
            heartbeat_interval_seconds=settings.letsplay.heartbeat_interval_seconds,
            lease_seconds=settings.letsplay.lease_seconds,
        ),
        consumer=consumer,
        producer=producer,
        session_factory=session_factory,
        handler=handler,
        sleep=_no_sleep,
    )
    return loop, broker, consumer


def _handler(
    youtube: FakeYouTubeAdapter,
    transcription: FakeTranscription,
    analyst: FakeAnalyst,
    *,
    instance_id: str = "letsplay-1",
    stt_enabled: bool = False,
    **letsplay_extra: Any,
) -> tuple[LetsPlayHandler, Settings]:
    settings = _settings(instance_id=instance_id, stt_enabled=stt_enabled, **letsplay_extra)
    return LetsPlayHandler(settings, youtube, transcription, analyst), settings


async def test_no_video_skips_agents(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(items=[])
    transcription = FakeTranscription()
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="lp-empty", settings=settings), settings)
    await loop.process_record(record)
    assert transcription.calls == []
    assert analyst.calls == []
    assert youtube.transcript_calls == []
    assert youtube.audio_calls == []
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.letsplay_status is LetsPlayStatus.no_video
    assert game.letsplay_conclusion is None
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded
    rows = await OutboxRepository(session).claim("letsplay", limit=10)
    assert len(rows) == 1
    data = rows[0].payload["data"]
    assert data["status"] == "no_video"
    assert data["conclusion"] is None
    assert consumer.committed[(record.topic, 0)] == 1


async def test_captions_ok_invokes_analyst_not_stt(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        transcripts={VIDEO_ID: _ok_transcript()},
    )
    transcription = FakeTranscription()
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_discovered(event_id="lp-ok", settings=settings), settings))
    assert transcription.calls == []
    assert youtube.audio_calls == []
    assert len(analyst.calls) == 1
    assert analyst.calls[0].transcript_excerpt == "The world is vast and the bosses are tough."
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.letsplay_status is LetsPlayStatus.ok
    assert game.letsplay_conclusion == "Блогер в восторге от мира."
    assert game.letsplay_highlights == ("исследование", "боссы")
    assert game.letsplay_video_title == "Elden Ring Let's Play"
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    rows = await OutboxRepository(session).claim("letsplay", limit=10)
    data = rows[0].payload["data"]
    assert data["status"] == "ok"
    assert data["conclusion"] == "Блогер в восторге от мира."
    assert rows[0].payload["source"] == "urn:games-intel:worker:letsplay"


async def test_stt_off_no_captions_skips_audio(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(items=[_hit()])
    transcription = FakeTranscription()
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst, stt_enabled=False)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_discovered(event_id="lp-nocap", settings=settings), settings)
    )
    assert youtube.audio_calls == []
    assert transcription.calls == []
    assert analyst.calls == []
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.letsplay_status is LetsPlayStatus.transcript_unavailable
    assert game.letsplay_video_url == f"https://www.youtube.com/watch?v={VIDEO_ID}"
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded


async def test_stt_on_uses_audio_then_analyst(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        audio={VIDEO_ID: AudioResult(status="ok", audio_ref="file://clip.wav")},
    )
    transcription = FakeTranscription(TranscriptionOutput(text="from stt", language="en"))
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst, stt_enabled=True)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_discovered(event_id="lp-stt", settings=settings), settings))
    assert len(youtube.audio_calls) == 1
    assert isinstance(youtube.audio_calls[0], GetAudioInput)
    assert (
        youtube.audio_calls[0].max_duration_seconds == settings.letsplay.max_video_duration_seconds
    )
    assert transcription.calls[0].audio_ref == "file://clip.wav"
    assert analyst.calls[0].transcript_excerpt == "from stt"


async def test_non_english_captions_use_stt_when_enabled(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        transcripts={
            VIDEO_ID: TranscriptResult(
                status="ok", language="ru", text="мир огромен", truncated=False
            )
        },
        audio={VIDEO_ID: AudioResult(status="ok", audio_ref="file://clip.wav")},
    )
    transcription = FakeTranscription(TranscriptionOutput(text="from stt english", language="en"))
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst, stt_enabled=True)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_discovered(event_id="lp-ru-cap", settings=settings), settings)
    )
    assert len(youtube.audio_calls) == 1
    assert transcription.calls[0].audio_ref == "file://clip.wav"
    assert analyst.calls[0].transcript_excerpt == "from stt english"


async def test_stt_fail_degrades_without_conclusion(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        audio={VIDEO_ID: AudioResult(status="ok", audio_ref="file://clip.wav")},
    )
    transcription = FakeTranscription(error=SttFailedError("stt down"))
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst, stt_enabled=True)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="lp-stt-fail", settings=settings), settings)
    await loop.process_record(record)
    assert analyst.calls == []
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.letsplay_status is LetsPlayStatus.transcript_unavailable
    assert game.letsplay_conclusion is None
    assert game.cover_url == COVER_URL
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded
    assert consumer.committed[(record.topic, 0)] == 1


async def test_quota_degrades_quota_exceeded(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        search_error=YoutubeAdapterError("quota_exceeded", "daily quota"),
    )
    transcription = FakeTranscription()
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="lp-quota", settings=settings), settings)
    await loop.process_record(record)
    assert transcription.calls == []
    assert analyst.calls == []
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.letsplay_status is LetsPlayStatus.quota_exceeded
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded
    rows = await OutboxRepository(session).claim("letsplay", limit=10)
    assert rows[0].payload["data"]["status"] == "quota_exceeded"
    assert consumer.committed[(record.topic, 0)] == 1


async def test_analyst_fail_failed_stage_no_conclusion(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        transcripts={VIDEO_ID: _ok_transcript()},
    )
    transcription = FakeTranscription()
    analyst = FakeAnalyst(error=AgentLlmStructureError("schema miss"))
    handler, settings = _handler(youtube, transcription, analyst)
    loop, broker, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="lp-llm", settings=settings), settings)
    await loop.process_record(record)
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.letsplay_conclusion is None
    assert game.cover_url == COVER_URL
    assert game.critic_summary == "Критики хвалят бой."
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.error_type == "LlmStructureError"
    assert await OutboxRepository(session).claim("letsplay", limit=10) == ()
    assert consumer.committed[(record.topic, 0)] == 1
    assert broker.topics.get(settings.event_name("dlq"))


async def test_does_not_clobber_reviews_or_catalog(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        transcripts={VIDEO_ID: _ok_transcript()},
    )
    handler, settings = _handler(youtube, FakeTranscription(), FakeAnalyst())
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_discovered(event_id="lp-keep", settings=settings), settings))
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.cover_url == COVER_URL
    assert game.developer == "FromSoftware"
    assert game.video_url == "https://www.youtube.com/watch?v=trailer"
    assert game.critic_summary == "Критики хвалят бой."
    assert game.user_summary == "Игрокам нравится мир."
    assert game.letsplay_status is LetsPlayStatus.ok


async def test_replay_discovered_is_letsplay_noop(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        transcripts={VIDEO_ID: _ok_transcript()},
    )
    transcription = FakeTranscription()
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, transcription, analyst)
    loop, _, consumer = _loop(session_factory, handler, settings)
    event = _discovered(event_id="lp-idem", settings=settings)
    await loop.process_record(_record(event, settings, offset=0))
    await loop.process_record(_record(event, settings, offset=1))
    assert len(analyst.calls) == 1
    assert len(youtube.search_calls) == 1
    _see_committed(session)
    rows = await OutboxRepository(session).claim("letsplay", limit=10)
    assert len(rows) == 1
    assert consumer.committed[(settings.event_name("game_cataloged"), 0)] == 2


async def test_two_replicas_one_persist(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        transcripts={VIDEO_ID: _ok_transcript()},
    )
    agent_a = FakeAnalyst()
    agent_b = FakeAnalyst()
    handler_a, settings_a = _handler(
        youtube, FakeTranscription(), agent_a, instance_id="letsplay-a"
    )
    handler_b, settings_b = _handler(
        youtube, FakeTranscription(), agent_b, instance_id="letsplay-b"
    )
    loop_a, _, _ = _loop(session_factory, handler_a, settings_a, instance_id="letsplay-a")
    loop_b, _, _ = _loop(session_factory, handler_b, settings_b, instance_id="letsplay-b")
    event = _discovered(event_id="lp-replica", settings=settings_a)
    await asyncio.gather(
        loop_a.process_record(_record(event, settings_a, offset=0)),
        loop_b.process_record(_record(event, settings_b, offset=1)),
    )
    assert 1 <= len(agent_a.calls) + len(agent_b.calls) <= 2
    _see_committed(session)
    rows = await OutboxRepository(session).claim("letsplay", limit=10)
    assert len(rows) == 1
    expected = (
        f"{settings_a.event_name('game_letsplay_analyzed')}:"
        f"{RUN_ID}:{SLUG}:{settings_a.letsplay.stage_name}"
    )
    assert rows[0].idempotency_key == expected


async def test_timeout_retries_then_succeeds(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = _FlakySearchPort(
        fail_times=2, items=[_hit()], transcripts={VIDEO_ID: _ok_transcript()}
    )
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, FakeTranscription(), analyst)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="lp-timeout", settings=settings), settings)
    await loop.process_record(record)
    assert youtube.attempts == 3
    assert len(analyst.calls) == 1
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    assert consumer.committed[(record.topic, 0)] == 1


async def test_timeout_does_not_commit_until_limit(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = _FlakySearchPort(fail_times=99, items=[_hit()])
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, FakeTranscription(), analyst)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="lp-timeout-fail", settings=settings), settings)
    await loop.process_record(record)
    assert analyst.calls == []
    assert youtube.attempts == settings.retry.max_attempts
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.letsplay)
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.error_type == "TransientError"
    assert await OutboxRepository(session).claim("letsplay", limit=10) == ()
    assert consumer.committed[(record.topic, 0)] == 1


async def test_worker_clips_transcript_before_analyst(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    long_text = "a" * 80
    youtube = FakeYouTubeAdapter(
        items=[_hit()],
        transcripts={VIDEO_ID: _ok_transcript(long_text)},
    )
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, FakeTranscription(), analyst, transcript_max_chars=40)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_discovered(event_id="lp-clip", settings=settings), settings))
    assert analyst.calls[0].transcript_excerpt == "a" * 40
    assert len(analyst.calls[0].transcript_excerpt) == 40


async def test_does_not_call_analyst_without_text(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    youtube = FakeYouTubeAdapter(items=[_hit()])
    analyst = FakeAnalyst()
    handler, settings = _handler(youtube, FakeTranscription(), analyst)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_discovered(event_id="lp-notext", settings=settings), settings)
    )
    assert analyst.calls == []


def test_clip_transcript() -> None:
    assert clip_transcript("hello", 10) == "hello"
    assert clip_transcript("hello world", 5) == "hello"


async def test_letsplay_topics_and_group_come_from_settings() -> None:
    settings = _settings()
    assert settings.letsplay.subscribe_event == "game_cataloged"
    assert settings.letsplay.publish_event == "game_letsplay_analyzed"
    assert settings.letsplay.stage_name == "letsplay"
    assert settings.consumer_group_id(settings.letsplay.consumer_group) == "games-intel.letsplay"
    assert settings.event_name(settings.letsplay.subscribe_event) == "game.cataloged"
    assert settings.event_name(settings.letsplay.publish_event) == "game.letsplay.analyzed"


def test_letsplay_does_not_import_langchain_or_build_prompts() -> None:
    for path in LETSPLAY_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "langchain" not in node.module
                assert "langgraph" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "langchain" not in alias.name
        text = path.read_text(encoding="utf-8")
        assert "letsplay_analyst_path" not in text
        assert "You are" not in text
        assert "googleapis.com/youtube" not in text


def test_letsplay_image_has_langchain_similarity_does_not() -> None:
    letsplay_toml = (REPO_ROOT / "apps/workers/letsplay/pyproject.toml").read_text(encoding="utf-8")
    similarity_toml = (REPO_ROOT / "apps/workers/similarity/pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert "langchain" in letsplay_toml
    assert "langgraph" in letsplay_toml
    assert "langchain" not in similarity_toml
    assert "langgraph" not in similarity_toml


class _FlakySearchPort(FakeYouTubeAdapter):
    def __init__(
        self,
        *,
        fail_times: int,
        items: list[VideoHit],
        transcripts: dict[str, TranscriptResult] | None = None,
    ) -> None:
        super().__init__(items=items, transcripts=transcripts)
        self._fail_times = fail_times
        self.attempts = 0

    async def search_letsplays(self, inp: SearchLetsPlaysInput) -> LetsPlaySearch:
        self.attempts += 1
        if self.attempts <= self._fail_times:
            raise YoutubeAdapterError("timeout", "transient")
        return await super().search_letsplays(inp)
