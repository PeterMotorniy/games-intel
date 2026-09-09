from __future__ import annotations

import ast
import asyncio
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.in_process import InProcessMetacriticAdapter
from games_intel.agents.review_summarizer.exceptions import (
    LlmStructureError as AgentLlmStructureError,
)
from games_intel.contracts import GameCataloged, ReviewSummarizerInput, build_cloud_event
from games_intel.contracts.adapters import GetReviewsInput, ReviewBatch, ReviewSnippet
from games_intel.contracts.agents import ReviewSummarizerOutput
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.payloads import ReviewSummary
from games_intel.db.records import CatalogSlice, PlatformScoreRecord
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import (
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionStage,
    RunTrigger,
)
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.serialization import encode_cloud_event
from games_intel.kafka.source import worker_source
from games_intel.kafka.testing import FakeBroker, FakeConsumer, FakeProducer
from games_intel.kafka.types import IncomingRecord
from games_intel.settings import Settings
from games_intel.workers.reviews.handler import ReviewsHandler

PROCESS_DATE = date(2026, 9, 8)
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-0000000000dd")
SLUG = "elden-ring"
COVER_URL = "/api/v1/media/covers/elden-ring"
REVIEWS_SRC = Path(__file__).resolve().parents[1] / "src" / "games_intel" / "workers" / "reviews"

_AGENT_OUTPUT = ReviewSummarizerOutput(
    critic=ReviewSummary(
        likes=["бой"],
        dislikes=["баги"],
        summary="Критики хвалят бой и мир.",
    ),
    user=ReviewSummary(
        likes=["атмосфера"],
        dislikes=["сложность"],
        summary="Игрокам нравится атмосфера.",
    ),
)


class FakeReviewSummarizer:
    def __init__(self, output: ReviewSummarizerOutput | None = None) -> None:
        self.calls: list[ReviewSummarizerInput] = []
        self.output = output if output is not None else _AGENT_OUTPUT

    async def ainvoke(self, inp: ReviewSummarizerInput) -> ReviewSummarizerOutput:
        self.calls.append(inp)
        return self.output


def _settings(*, instance_id: str = "reviews-1") -> Settings:
    base = Settings()
    retry = base.retry.model_copy(
        update={"max_attempts": 3, "backoff_base_seconds": 0, "jitter_ratio": 0}
    )
    reviews = base.reviews.model_copy(update={"instance_id": instance_id})
    return base.model_copy(update={"retry": retry, "reviews": reviews})


def _snippet(
    excerpt: str, *, author: str | None = "IGN", score: float | None = 90
) -> ReviewSnippet:
    return ReviewSnippet(author=author, score=score, excerpt=excerpt, published_at=None)


def _batch(*excerpts: str) -> ReviewBatch:
    return ReviewBatch(
        items=[_snippet(text, author=f"author-{index}") for index, text in enumerate(excerpts)],
        truncated=False,
    )


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
        loaded.reviews.subscribe_event,
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
        topic=settings.event_name(settings.reviews.subscribe_event),
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
            video_url="https://www.youtube.com/watch?v=abc123",
            platforms=(PlatformScoreRecord(platform_code="ps5", metascore=96, userscore=None),),
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
    handler: ReviewsHandler,
    settings: Settings,
    *,
    instance_id: str = "reviews-1",
) -> tuple[DaemonLoop, FakeBroker, FakeConsumer]:
    broker = FakeBroker()
    consumer = FakeConsumer(broker, (settings.event_name(settings.reviews.subscribe_event),))
    producer = FakeProducer(broker)
    loop = DaemonLoop(
        settings,
        DaemonConfig(
            worker_type="reviews",
            instance_id=instance_id,
            stage_name=settings.reviews.stage_name,
            subscribe_event_key=settings.reviews.subscribe_event,
            heartbeat_interval_seconds=settings.reviews.heartbeat_interval_seconds,
            lease_seconds=settings.reviews.lease_seconds,
        ),
        consumer=consumer,
        producer=producer,
        session_factory=session_factory,
        handler=handler,
        sleep=_no_sleep,
    )
    return loop, broker, consumer


def _handler(
    port: InProcessMetacriticAdapter,
    agent: FakeReviewSummarizer,
    *,
    instance_id: str = "reviews-1",
) -> tuple[ReviewsHandler, Settings]:
    settings = _settings(instance_id=instance_id)
    return ReviewsHandler(settings, port, agent), settings


async def test_empty_reviews_skip_agent_and_degrade(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter()
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="rev-empty", settings=settings), settings)
    await loop.process_record(record)
    assert agent.calls == []
    critic_calls = [call for call in port.calls if call[0] == "get_critic_reviews"]
    user_calls = [call for call in port.calls if call[0] == "get_user_reviews"]
    assert len(critic_calls) == 1
    assert len(user_calls) == 1
    critic_inp = critic_calls[0][1]
    user_inp = user_calls[0][1]
    assert isinstance(critic_inp, GetReviewsInput)
    assert critic_inp.limit == settings.reviews.critic_limit
    assert critic_inp.max_chars == settings.reviews.max_chars
    assert user_inp.limit == settings.reviews.user_limit
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.cover_url == COVER_URL
    assert game.critic_likes == ()
    assert game.critic_dislikes == ()
    assert game.critic_summary == ""
    assert game.user_summary == ""
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded
    rows = await OutboxRepository(session).claim("reviews", limit=10)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["type"] == settings.event_name("game_reviews_summarized")
    assert payload["source"] == "urn:games-intel:worker:reviews"
    data = payload["data"]
    assert data["degraded"] is True
    assert data["critic_review_count"] == 0
    assert data["user_review_count"] == 0
    assert data["critic"] == {"likes": [], "dislikes": [], "summary": ""}
    assert consumer.committed[(record.topic, 0)] == 1
    heartbeats = await IngestionRepository(session).list_heartbeats()
    reviews_beats = [row for row in heartbeats if row.worker_type == "reviews"]
    assert len(reviews_beats) == 1
    assert reviews_beats[0].instance_id == "reviews-1"


async def test_one_side_empty_does_not_keep_hallucinated_summary(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(user_reviews={SLUG: _batch("Tough bosses.")})
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_discovered(event_id="rev-one-side", settings=settings), settings)
    )
    assert len(agent.calls) == 1
    assert agent.calls[0].critic == []
    assert [item.excerpt for item in agent.calls[0].user] == ["Tough bosses."]
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.critic_likes == ()
    assert game.critic_summary == ""
    assert game.user_summary == "Игрокам нравится атмосфера."
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded
    rows = await OutboxRepository(session).claim("reviews", limit=10)
    data = rows[0].payload["data"]
    assert data["degraded"] is True
    assert data["critic_review_count"] == 0
    assert data["user_review_count"] == 1
    assert data["critic"] == {"likes": [], "dislikes": [], "summary": ""}


async def test_non_empty_invokes_agent_and_persists(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(
        critic_reviews={SLUG: _batch("Great combat.")},
        user_reviews={SLUG: _batch("Tough bosses.")},
    )
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_discovered(event_id="rev-ok", settings=settings), settings))
    assert len(agent.calls) == 1
    assert [item.excerpt for item in agent.calls[0].critic] == ["Great combat."]
    assert [item.excerpt for item in agent.calls[0].user] == ["Tough bosses."]
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.cover_url == COVER_URL
    assert game.developer == "FromSoftware"
    assert game.critic_likes == ("бой",)
    assert game.critic_dislikes == ("баги",)
    assert game.critic_summary == "Критики хвалят бой и мир."
    assert game.user_likes == ("атмосфера",)
    assert game.user_summary == "Игрокам нравится атмосфера."
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    rows = await OutboxRepository(session).claim("reviews", limit=10)
    data = rows[0].payload["data"]
    assert data["degraded"] is False
    assert data["critic_review_count"] == 1
    assert data["user_review_count"] == 1
    assert data["critic"]["summary"] == "Критики хвалят бой и мир."


async def test_reviews_does_not_clobber_cover(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(
        critic_reviews={SLUG: _batch("ok")},
        user_reviews={SLUG: _batch("ok")},
    )
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_discovered(event_id="rev-cover", settings=settings), settings)
    )
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.cover_url == COVER_URL
    assert game.cover_source_url == "https://static.metacritic.com/images/elden-ring.jpg"
    assert game.video_url == "https://www.youtube.com/watch?v=abc123"


async def test_replay_discovered_is_reviews_noop(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(
        critic_reviews={SLUG: _batch("ok")},
        user_reviews={SLUG: _batch("ok")},
    )
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, consumer = _loop(session_factory, handler, settings)
    event = _discovered(event_id="rev-idem", settings=settings)
    await loop.process_record(_record(event, settings, offset=0))
    await loop.process_record(_record(event, settings, offset=1))
    assert len(agent.calls) == 1
    critic_calls = [call for call in port.calls if call[0] == "get_critic_reviews"]
    assert len(critic_calls) == 1
    _see_committed(session)
    rows = await OutboxRepository(session).claim("reviews", limit=10)
    assert len(rows) == 1
    assert consumer.committed[(settings.event_name("game_cataloged"), 0)] == 2


async def test_two_replicas_one_persist(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(
        critic_reviews={SLUG: _batch("ok")},
        user_reviews={SLUG: _batch("ok")},
    )
    agent_a = FakeReviewSummarizer()
    agent_b = FakeReviewSummarizer()
    handler_a, settings_a = _handler(port, agent_a, instance_id="reviews-a")
    handler_b, settings_b = _handler(port, agent_b, instance_id="reviews-b")
    loop_a, _, _ = _loop(session_factory, handler_a, settings_a, instance_id="reviews-a")
    loop_b, _, _ = _loop(session_factory, handler_b, settings_b, instance_id="reviews-b")
    event = _discovered(event_id="rev-replica", settings=settings_a)
    await asyncio.gather(
        loop_a.process_record(_record(event, settings_a, offset=0)),
        loop_b.process_record(_record(event, settings_b, offset=1)),
    )
    assert 1 <= len(agent_a.calls) + len(agent_b.calls) <= 2
    _see_committed(session)
    rows = await OutboxRepository(session).claim("reviews", limit=10)
    assert len(rows) == 1
    expected = (
        f"{settings_a.event_name('game_reviews_summarized')}:"
        f"{RUN_ID}:{SLUG}:{settings_a.reviews.stage_name}"
    )
    assert rows[0].idempotency_key == expected


async def test_timeout_retries_then_succeeds(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = _FlakyReviewsPort(fail_times=2, batch=_batch("ok"))
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="rev-timeout", settings=settings), settings)
    await loop.process_record(record)
    assert port.attempts == 3
    assert len(agent.calls) == 1
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    assert consumer.committed[(record.topic, 0)] == 1


async def test_user_timeout_still_summarizes_critic_reviews(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)

    class _UserTimeoutPort(InProcessMetacriticAdapter):
        async def get_user_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
            del inp
            raise MetacriticAdapterError("timeout", "user side down")

    port = _UserTimeoutPort(critic_reviews={SLUG: _batch("Great combat.")})
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_discovered(event_id="rev-user-timeout", settings=settings), settings)
    )
    assert len(agent.calls) == 1
    assert [item.excerpt for item in agent.calls[0].critic] == ["Great combat."]
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.critic_summary == "Критики хвалят бой и мир."


async def test_timeout_does_not_commit_until_limit(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = _FlakyReviewsPort(fail_times=99, batch=_batch("ok"))
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="rev-timeout-fail", settings=settings), settings)
    await loop.process_record(record)
    assert agent.calls == []
    assert port.attempts == settings.retry.max_attempts
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.error_type == "TransientError"
    assert await OutboxRepository(session).claim("reviews", limit=10) == ()
    assert consumer.committed[(record.topic, 0)] == 1


async def test_reviews_succeed_when_catalog_stage_failed(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    ingestion = IngestionRepository(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    await ingestion.upsert_item(
        run_id=RUN_ID,
        metacritic_slug=SLUG,
        process_date=PROCESS_DATE,
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.failed,
        game_id=game.id,
        event_id="cat-404",
        error_type="NotFoundError",
        error_message="gone",
    )
    await session.commit()
    port = InProcessMetacriticAdapter(
        critic_reviews={SLUG: _batch("ok")},
        user_reviews={SLUG: _batch("ok")},
    )
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, _, _ = _loop(session_factory, handler, settings)
    event = _discovered(event_id="rev-after-404", settings=settings)
    await loop.process_record(_record(event, settings))
    _see_committed(session)
    reviews_item = await ingestion.get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert reviews_item is not None
    assert reviews_item.status is IngestionItemStatus.completed
    catalog_item = await ingestion.get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    assert catalog_item is not None
    assert catalog_item.status is IngestionItemStatus.failed
    assert len(agent.calls) == 1


async def test_parse_error_fails_item(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(
        errors={"get_critic_reviews:elden-ring": MetacriticAdapterError("parse_error", "broken")}
    )
    agent = FakeReviewSummarizer()
    handler, settings = _handler(port, agent)
    loop, broker, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="rev-parse", settings=settings), settings)
    await loop.process_record(record)
    assert agent.calls == []
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.error_type == "ParseError"
    catalog_item = await IngestionRepository(session).get_item(
        RUN_ID, SLUG, IngestionStage.discovered
    )
    assert catalog_item is not None
    assert catalog_item.status is IngestionItemStatus.completed
    assert await OutboxRepository(session).claim("reviews", limit=10) == ()
    assert consumer.committed[(record.topic, 0)] == 1
    assert broker.topics.get(settings.event_name("dlq"))


async def test_llm_schema_error_fails_item(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(
        critic_reviews={SLUG: _batch("critic text")},
        user_reviews={SLUG: _batch("user text")},
    )

    class _FailingAgent:
        async def ainvoke(self, inp: ReviewSummarizerInput) -> ReviewSummarizerOutput:
            raise AgentLlmStructureError("structured output invalid after retries")

    handler, settings = _handler(port, _FailingAgent())  # type: ignore[arg-type]
    loop, broker, consumer = _loop(session_factory, handler, settings)
    record = _record(_discovered(event_id="rev-schema", settings=settings), settings)
    await loop.process_record(record)
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.reviews)
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.error_type == "LlmStructureError"
    assert await OutboxRepository(session).claim("reviews", limit=10) == ()
    assert consumer.committed[(record.topic, 0)] == 1
    assert broker.topics.get(settings.event_name("dlq"))


async def test_reviews_topics_and_group_come_from_settings() -> None:
    settings = _settings()
    assert settings.reviews.subscribe_event == "game_cataloged"
    assert settings.reviews.publish_event == "game_reviews_summarized"
    assert settings.reviews.stage_name == "reviews"
    assert settings.consumer_group_id(settings.reviews.consumer_group) == "games-intel.reviews"
    assert settings.event_name(settings.reviews.subscribe_event) == "game.cataloged"
    assert settings.event_name(settings.reviews.publish_event) == "game.reviews.summarized"


def test_reviews_does_not_import_langchain_or_build_prompts() -> None:
    for path in REVIEWS_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "langchain" not in node.module
                assert "langgraph" not in node.module
                assert "playwright" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "langchain" not in alias.name
                    assert "playwright" not in alias.name
        text = path.read_text(encoding="utf-8")
        assert "review_summarizer_path" not in text
        assert "You are" not in text
        assert "c-siteReview" not in text


class _FlakyReviewsPort(InProcessMetacriticAdapter):
    def __init__(self, *, fail_times: int, batch: ReviewBatch) -> None:
        super().__init__(critic_reviews={SLUG: batch}, user_reviews={SLUG: batch})
        self._fail_times = fail_times
        self.attempts = 0

    async def get_critic_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        self.attempts += 1
        if self.attempts <= self._fail_times:
            raise MetacriticAdapterError("timeout", "transient")
        return await super().get_critic_reviews(inp)

    async def get_user_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        if self.attempts <= self._fail_times:
            raise MetacriticAdapterError("timeout", "transient")
        return await super().get_user_reviews(inp)
