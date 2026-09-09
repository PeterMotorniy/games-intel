from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.adapters.embeddings.fake import FakeEmbeddingAdapter
from games_intel.contracts import (
    GameCataloged,
    GameReviewsSummarized,
    ReviewSummary,
    SimilarityRecomputeRequested,
    build_cloud_event,
)
from games_intel.contracts.envelope import CloudEvent
from games_intel.db.records import CatalogSlice, PlatformScoreRecord, ReviewsSlice
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.reviews import GameReviewsRepository
from games_intel.db.repositories.similar import SimilarGamesRepository
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
from games_intel.workers.similarity.handler import SimilarityHandler

PROCESS_DATE = date(2026, 9, 8)
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-0000000000dd")
RUN_ID_2 = UUID("0191c0aa-7e3b-7000-8000-0000000000ee")
SIM_SRC = Path(__file__).resolve().parents[1] / "src" / "games_intel" / "workers" / "similarity"


def _vec(*ones: int, dim: int = 768) -> list[float]:
    values = [0.0] * dim
    for index in ones:
        values[index] = 1.0
    return values


def _settings(*, mode: str = "inline_all", k: int = 5, reviews: bool = True) -> Settings:
    base = Settings()
    similarity = base.similarity.model_copy(
        update={
            "instance_id": "similarity-1",
            "mode": mode,
            "k": k,
            "recompute_on_reviews": reviews,
            "emit_assigned_for_all": False,
        }
    )
    embeddings = base.embeddings.model_copy(update={"model": "fake-embed", "vector_dim": 768})
    retry = base.retry.model_copy(
        update={"max_attempts": 3, "backoff_base_seconds": 0, "jitter_ratio": 0}
    )
    return base.model_copy(
        update={"similarity": similarity, "embeddings": embeddings, "retry": retry}
    )


def _catalog_slice(slug: str, title: str) -> CatalogSlice:
    return CatalogSlice(
        metacritic_slug=slug,
        title=title,
        listing_url=f"https://www.metacritic.com/game/{slug}/",
        developer="Studio",
        publisher="Pub",
        genres=("Action", "RPG"),
        release_date=date(2022, 2, 25),
        description=f"{title} description",
        platforms=(PlatformScoreRecord(platform_code="ps5", metascore=90, userscore=None),),
    )


async def _seed_game(
    session: AsyncSession,
    *,
    slug: str,
    title: str,
    run_id: UUID = RUN_ID,
    reviews: bool = False,
) -> None:
    ingestion = IngestionRepository(session)
    if await ingestion.get_run(run_id) is None:
        await ingestion.create_run(
            process_date=PROCESS_DATE,
            source="new_releases",
            page=None,
            limit=20,
            trigger=RunTrigger.cron,
            run_id=run_id,
            status=IngestionRunStatus.completed,
        )
    catalog = GameCatalogRepository(session)
    game_id = await catalog.upsert_catalog(_catalog_slice(slug, title))
    await ingestion.upsert_item(
        run_id=run_id,
        metacritic_slug=slug,
        process_date=PROCESS_DATE,
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.completed,
        game_id=game_id,
        event_id=f"cat-{slug}",
    )
    if reviews:
        await GameReviewsRepository(session).update_reviews(
            ReviewsSlice(
                metacritic_slug=slug,
                critic_likes=("combat",),
                critic_dislikes=(),
                critic_summary="Critics like combat.",
                user_likes=("world",),
                user_dislikes=(),
                user_summary="Users like the world.",
            )
        )
    await session.commit()
    session.expire_all()


def _cataloged(
    settings: Settings,
    *,
    event_id: str,
    slug: str,
    title: str,
    run_id: UUID = RUN_ID,
) -> CloudEvent[Any]:
    data = GameCataloged(
        run_id=run_id,
        process_date=PROCESS_DATE,
        metacritic_slug=slug,
        title=title,
        developer="Studio",
        publisher="Pub",
        genres=["Action", "RPG"],
        release_date=date(2022, 2, 25),
        description=f"{title} description",
        platforms=[],
    )
    return build_cloud_event(
        settings,
        settings.similarity.subscribe_event,
        source=worker_source(settings, "catalog"),
        subject=slug,
        data=data,
        stage="cataloged",
        run_id=run_id,
        event_id=event_id,
        occurred_at=NOW,
    )


def _reviews(
    settings: Settings,
    *,
    event_id: str,
    slug: str,
    run_id: UUID = RUN_ID,
) -> CloudEvent[Any]:
    data = GameReviewsSummarized(
        run_id=run_id,
        metacritic_slug=slug,
        critic=ReviewSummary(likes=["combat"], dislikes=[], summary="Critics like combat."),
        user=ReviewSummary(likes=["world"], dislikes=[], summary="Users like the world."),
        critic_review_count=2,
        user_review_count=2,
        degraded=False,
    )
    return build_cloud_event(
        settings,
        settings.similarity.subscribe_reviews_event,
        source=worker_source(settings, "reviews"),
        subject=slug,
        data=data,
        stage="reviews",
        run_id=run_id,
        event_id=event_id,
        occurred_at=NOW,
    )


def _recompute(
    settings: Settings,
    *,
    event_id: str,
    scope: str,
    when: datetime = NOW,
    candidate_slugs: list[str] | None = None,
    center_slug: str | None = None,
    reason: str = "schedule",
    run_id: UUID | None = None,
    idempotency_key: str | None = None,
) -> CloudEvent[Any]:
    hour_stamp = when.strftime("%Y-%m-%dT%H")
    data = SimilarityRecomputeRequested(
        run_id=run_id,
        process_date=PROCESS_DATE,
        scope=scope,  # type: ignore[arg-type]
        center_slug=center_slug,
        candidate_slugs=candidate_slugs or [],
        reason=reason,  # type: ignore[arg-type]
    )
    subject = center_slug or f"{hour_stamp}:all"
    key = idempotency_key or (
        f"{settings.event_name('similarity_recompute')}:"
        f"{PROCESS_DATE.isoformat()}:{hour_stamp}:all:recompute"
    )
    return build_cloud_event(
        settings,
        settings.similarity.subscribe_recompute_event,
        source=worker_source(settings, "scheduler"),
        subject=subject,
        data=data,
        stage="recompute",
        run_id=run_id,
        event_id=event_id,
        occurred_at=when,
        idempotency_key=key,
    )


def _record(event: CloudEvent[Any], topic: str, *, offset: int = 0) -> IncomingRecord:
    return IncomingRecord(
        topic=topic,
        partition=0,
        offset=offset,
        key=event.subject,
        value=encode_cloud_event(event),
    )


async def _no_sleep(_delay: float) -> None:
    return None


def _loop(
    session_factory: async_sessionmaker[AsyncSession],
    handler: SimilarityHandler,
    settings: Settings,
) -> tuple[DaemonLoop, FakeBroker, FakeConsumer]:
    broker = FakeBroker()
    topics = (
        settings.event_name(settings.similarity.subscribe_event),
        settings.event_name(settings.similarity.subscribe_reviews_event),
        settings.event_name(settings.similarity.subscribe_recompute_event),
    )
    consumer = FakeConsumer(broker, topics)
    producer = FakeProducer(broker)
    loop = DaemonLoop(
        settings,
        DaemonConfig(
            worker_type="similarity",
            instance_id=settings.similarity.instance_id,
            stage_name=settings.similarity.stage_name,
            subscribe_event_key=settings.similarity.subscribe_event,
            extra_subscribe_event_keys=(
                settings.similarity.subscribe_reviews_event,
                settings.similarity.subscribe_recompute_event,
            ),
            lease_seconds=settings.similarity.lease_seconds,
        ),
        consumer=consumer,
        producer=producer,
        session_factory=session_factory,
        handler=handler,
        sleep=_no_sleep,
    )
    return loop, broker, consumer


def _see_committed(session: AsyncSession) -> None:
    session.expire_all()


async def test_two_games_are_mutual_neighbors_inline_all(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest")
    await _seed_game(session, slug="beta", title="Beta Quest")
    settings = _settings(k=5)
    fake = FakeEmbeddingAdapter(
        settings,
        vectors={"Alpha Quest": _vec(0), "Beta Quest": _vec(1)},
    )
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    topic = settings.event_name(settings.similarity.subscribe_event)
    await loop.process_record(
        _record(_cataloged(settings, event_id="sim-a", slug="alpha", title="Alpha Quest"), topic)
    )
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="sim-b", slug="beta", title="Beta Quest"),
            topic,
            offset=1,
        )
    )
    _see_committed(session)
    similar = SimilarGamesRepository(session)
    a_neighbors = await similar.list_for_slug("alpha")
    b_neighbors = await similar.list_for_slug("beta")
    assert [row.metacritic_slug for row in a_neighbors] == ["beta"]
    assert [row.metacritic_slug for row in b_neighbors] == ["alpha"]
    assert all(row.metacritic_slug != "alpha" for row in a_neighbors)
    item = await IngestionRepository(session).get_item(RUN_ID, "beta", IngestionStage.similar)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    rows = await OutboxRepository(session).claim("similarity", limit=10)
    assigned_type = settings.event_name("game_similar_assigned")
    types = {row.payload["type"] for row in rows}
    assert assigned_type in types
    assigned = [row for row in rows if row.payload["type"] == assigned_type]
    assert any(row.payload["data"]["metacritic_slug"] == "beta" for row in assigned)


async def test_third_game_displaces_rank_k(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest")
    await _seed_game(session, slug="beta", title="Beta Quest")
    await _seed_game(session, slug="gamma", title="Gamma Quest")
    settings = _settings(k=1)
    fake = FakeEmbeddingAdapter(
        settings,
        vectors={
            "Alpha Quest": _vec(0),
            "Beta Quest": _vec(8),
            "Gamma Quest": _vec(0, 1),
        },
    )
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    topic = settings.event_name(settings.similarity.subscribe_event)
    await loop.process_record(
        _record(_cataloged(settings, event_id="k-a", slug="alpha", title="Alpha Quest"), topic)
    )
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="k-b", slug="beta", title="Beta Quest"),
            topic,
            offset=1,
        )
    )
    _see_committed(session)
    similar = SimilarGamesRepository(session)
    assert [row.metacritic_slug for row in await similar.list_for_slug("alpha")] == ["beta"]
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="k-c", slug="gamma", title="Gamma Quest"),
            topic,
            offset=2,
        )
    )
    _see_committed(session)
    assert [row.metacritic_slug for row in await similar.list_for_slug("alpha")] == ["gamma"]


async def test_hash_unchanged_skips_fake_embed(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest")
    await IngestionRepository(session).create_run(
        process_date=PROCESS_DATE,
        source="browse",
        page=1,
        limit=20,
        trigger=RunTrigger.manual,
        run_id=RUN_ID_2,
        status=IngestionRunStatus.completed,
    )
    await session.commit()
    settings = _settings()
    fake = FakeEmbeddingAdapter(settings, vectors={"Alpha Quest": _vec(0)})
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    topic = settings.event_name(settings.similarity.subscribe_event)
    first = _cataloged(settings, event_id="hash-1", slug="alpha", title="Alpha Quest")
    await loop.process_record(_record(first, topic))
    assert len(fake.calls) == 1
    second = _cataloged(
        settings, event_id="hash-2", slug="alpha", title="Alpha Quest", run_id=RUN_ID_2
    )
    await loop.process_record(_record(second, topic, offset=1))
    assert len(fake.calls) == 1


async def test_missing_embedding_is_degraded_empty_list(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ingestion = IngestionRepository(session)
    await ingestion.create_run(
        process_date=PROCESS_DATE,
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.cron,
        run_id=RUN_ID,
        status=IngestionRunStatus.completed,
    )
    game_id, _ = await GameCatalogRepository(session).ensure_game_stub(
        metacritic_slug="blank",
        title="   ",
    )
    await ingestion.upsert_item(
        run_id=RUN_ID,
        metacritic_slug="blank",
        process_date=PROCESS_DATE,
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.completed,
        game_id=game_id,
        event_id="cat-blank",
    )
    await session.commit()
    settings = _settings()
    fake = FakeEmbeddingAdapter(settings)
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    topic = settings.event_name(settings.similarity.subscribe_event)
    await loop.process_record(
        _record(_cataloged(settings, event_id="blank-1", slug="blank", title="   "), topic)
    )
    _see_committed(session)
    assert fake.calls == []
    neighbors = await SimilarGamesRepository(session).list_for_slug("blank")
    assert neighbors == ()
    item = await IngestionRepository(session).get_item(RUN_ID, "blank", IngestionStage.similar)
    assert item is not None
    assert item.status is IngestionItemStatus.degraded


async def test_no_neighbors_completed_empty_list(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="solo", title="Solo Quest")
    settings = _settings()
    fake = FakeEmbeddingAdapter(settings, vectors={"Solo Quest": _vec(0)})
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    topic = settings.event_name(settings.similarity.subscribe_event)
    await loop.process_record(
        _record(_cataloged(settings, event_id="solo-1", slug="solo", title="Solo Quest"), topic)
    )
    _see_committed(session)
    neighbors = await SimilarGamesRepository(session).list_for_slug("solo")
    assert neighbors == ()
    item = await IngestionRepository(session).get_item(RUN_ID, "solo", IngestionStage.similar)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    rows = await OutboxRepository(session).claim("similarity", limit=10)
    assigned = [
        row for row in rows if row.payload["type"] == settings.event_name("game_similar_assigned")
    ]
    assert assigned[0].payload["data"]["items"] == []


async def test_one_other_game_is_k_one(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest")
    await _seed_game(session, slug="beta", title="Beta Quest")
    settings = _settings(k=5)
    fake = FakeEmbeddingAdapter(settings, vectors={"Alpha Quest": _vec(0), "Beta Quest": _vec(1)})
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    topic = settings.event_name(settings.similarity.subscribe_event)
    await loop.process_record(
        _record(_cataloged(settings, event_id="one-a", slug="alpha", title="Alpha Quest"), topic)
    )
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="one-b", slug="beta", title="Beta Quest"),
            topic,
            offset=1,
        )
    )
    _see_committed(session)
    neighbors = await SimilarGamesRepository(session).list_for_slug("alpha")
    assert len(neighbors) == 1
    assert neighbors[0].rank == 1


async def test_neighbors_handler_does_not_write_second_recompute(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest")
    await _seed_game(session, slug="beta", title="Beta Quest")
    settings = _settings(mode="incremental", k=5)
    fake = FakeEmbeddingAdapter(settings, vectors={"Alpha Quest": _vec(0), "Beta Quest": _vec(1)})
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    catalog_topic = settings.event_name(settings.similarity.subscribe_event)
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="inc-a", slug="alpha", title="Alpha Quest"),
            catalog_topic,
        )
    )
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="inc-b", slug="beta", title="Beta Quest"),
            catalog_topic,
            offset=1,
        )
    )
    _see_committed(session)
    rows = await OutboxRepository(session).claim("similarity", limit=20)
    recompute_topic = settings.event_name("similarity_recompute")
    recomputes = [row for row in rows if row.payload["type"] == recompute_topic]
    assert len(recomputes) == 1
    payload = recomputes[0].payload["data"]
    assert payload["scope"] == "neighbors"
    assert payload["center_slug"] == "beta"
    await OutboxRepository(session).mark_published([row.id for row in rows])
    await session.commit()
    event = _recompute(
        settings,
        event_id="neigh-1",
        scope="neighbors",
        candidate_slugs=list(payload["candidate_slugs"]),
        center_slug="beta",
        reason="cataloged",
        run_id=RUN_ID,
        idempotency_key=f"{recompute_topic}:{RUN_ID}:beta:neighbors",
    )
    await loop.process_record(_record(event, recompute_topic, offset=2))
    _see_committed(session)
    later = await OutboxRepository(session).claim("similarity", limit=20)
    second = [row for row in later if row.payload["type"] == recompute_topic]
    assert second == []


async def test_hourly_full_recompute_is_noop_on_replay(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest")
    await _seed_game(session, slug="beta", title="Beta Quest")
    settings = _settings()
    fake = FakeEmbeddingAdapter(settings, vectors={"Alpha Quest": _vec(0), "Beta Quest": _vec(1)})
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    catalog_topic = settings.event_name(settings.similarity.subscribe_event)
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="hr-a", slug="alpha", title="Alpha Quest"),
            catalog_topic,
        )
    )
    await loop.process_record(
        _record(
            _cataloged(settings, event_id="hr-b", slug="beta", title="Beta Quest"),
            catalog_topic,
            offset=1,
        )
    )
    embed_calls = len(fake.calls)
    recompute_topic = settings.event_name("similarity_recompute")
    first = _recompute(settings, event_id="full-1", scope="all")
    await loop.process_record(_record(first, recompute_topic, offset=2))
    second = _recompute(settings, event_id="full-2", scope="all")
    assert first.idempotencykey == second.idempotencykey
    assert first.id != second.id
    await loop.process_record(_record(second, recompute_topic, offset=3))
    assert len(fake.calls) == embed_calls


async def test_full_recompute_embeds_games_missing_vectors(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest")
    await _seed_game(session, slug="beta", title="Beta Quest")
    settings = _settings(k=1)
    fake = FakeEmbeddingAdapter(settings, vectors={"Alpha Quest": _vec(0), "Beta Quest": _vec(1)})
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, _ = _loop(session_factory, handler, settings)
    recompute_topic = settings.event_name("similarity_recompute")
    await loop.process_record(
        _record(_recompute(settings, event_id="full-missing", scope="all"), recompute_topic)
    )
    assert len(fake.calls) == 2
    _see_committed(session)
    similar = SimilarGamesRepository(session)
    alpha = await similar.list_for_slug("alpha")
    beta = await similar.list_for_slug("beta")
    assert [row.metacritic_slug for row in alpha] == ["beta"]
    assert [row.metacritic_slug for row in beta] == ["alpha"]


async def test_reviews_ignored_when_flag_false(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_game(session, slug="alpha", title="Alpha Quest", reviews=True)
    settings = _settings(reviews=False)
    fake = FakeEmbeddingAdapter(settings, vectors={"Alpha Quest": _vec(0)})
    handler = SimilarityHandler(settings, fake, session_factory=session_factory)
    loop, _, consumer = _loop(session_factory, handler, settings)
    topic = settings.event_name(settings.similarity.subscribe_reviews_event)
    record = _record(_reviews(settings, event_id="rev-1", slug="alpha"), topic)
    await loop.process_record(record)
    assert fake.calls == []
    assert consumer.committed[(topic, 0)] == 1
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, "alpha", IngestionStage.similar)
    assert item is None


async def test_topics_and_group_come_from_settings() -> None:
    settings = _settings()
    assert (
        settings.consumer_group_id(settings.similarity.consumer_group) == "games-intel.similarity"
    )
    assert settings.event_name(settings.similarity.subscribe_event) == "game.cataloged"
    assert (
        settings.event_name(settings.similarity.subscribe_reviews_event)
        == "game.reviews.summarized"
    )
    assert settings.event_name(settings.similarity.subscribe_recompute_event) == (
        "similarity.recompute.requested"
    )
    assert settings.event_name(settings.similarity.publish_event) == "game.similar.assigned"


def test_similarity_does_not_import_langchain() -> None:
    for path in SIM_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "langchain" not in node.module
                assert "langgraph" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "langchain" not in alias.name
                    assert "langgraph" not in alias.name
