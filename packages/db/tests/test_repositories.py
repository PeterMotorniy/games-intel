from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.db.models import DailyProcessedSlug, ProcessedEvent
from games_intel.db.records import (
    CatalogSlice,
    LetsPlaySlice,
    OutboxInsert,
    PlatformScoreRecord,
    ReviewsSlice,
    SimilarNeighbor,
)
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.letsplay import GameLetsPlayRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.page_cache import PageCacheRepository
from games_intel.db.repositories.reviews import GameReviewsRepository
from games_intel.db.repositories.similar import SimilarGamesRepository
from games_intel.db.types import (
    GameSort,
    IngestionItemStatus,
    IngestionStage,
    InsertOutcome,
    LetsPlayStatus,
    RunTrigger,
)


def _catalog(
    slug: str,
    title: str,
    *,
    cover_url: str | None = "/api/v1/media/covers/x",
    platforms: tuple[PlatformScoreRecord, ...] = (),
) -> CatalogSlice:
    return CatalogSlice(
        metacritic_slug=slug,
        title=title,
        listing_url=f"https://www.metacritic.com/game/{slug}/",
        cover_url=cover_url,
        cover_source_url=f"https://cdn.example/{slug}.jpg",
        developer="FromSoftware",
        publisher="Bandai",
        genres=("Action", "RPG"),
        release_date=date(2022, 2, 25),
        description="An open-world action RPG.",
        video_url="https://www.youtube.com/watch?v=abc",
        platforms=platforms
        or (
            PlatformScoreRecord(platform_code="ps5", metascore=96, userscore=Decimal("7.8")),
            PlatformScoreRecord(platform_code="pc", metascore=94, userscore=Decimal("6.4")),
        ),
    )


async def test_reviews_update_does_not_change_cover(session: AsyncSession) -> None:
    catalog = GameCatalogRepository(session)
    reviews = GameReviewsRepository(session)
    await catalog.upsert_catalog(_catalog("elden-ring", "Elden Ring", cover_url="/covers/elden"))
    await reviews.update_reviews(
        ReviewsSlice(
            metacritic_slug="elden-ring",
            critic_likes=("combat",),
            critic_dislikes=("performance",),
            critic_summary="Great combat.",
            user_likes=("exploration",),
            user_dislikes=("difficulty",),
            user_summary="Harsh but fair.",
        )
    )
    game = await catalog.get_by_slug("elden-ring")
    assert game is not None
    assert game.cover_url == "/covers/elden"
    assert game.cover_source_url == "https://cdn.example/elden-ring.jpg"
    assert game.developer == "FromSoftware"
    assert game.critic_summary == "Great combat."
    assert game.user_likes == ("exploration",)


async def test_letsplay_does_not_clobber_catalog(session: AsyncSession) -> None:
    catalog = GameCatalogRepository(session)
    letsplay = GameLetsPlayRepository(session)
    await catalog.upsert_catalog(_catalog("sekiro", "Sekiro"))
    await letsplay.update_letsplay(
        LetsPlaySlice(
            metacritic_slug="sekiro",
            status=LetsPlayStatus.ok,
            video_url="https://www.youtube.com/watch?v=lp",
            video_title="Let's Play Sekiro",
            view_count=1_000_000,
            conclusion="Precise combat.",
            highlights=("deflect",),
        )
    )
    game = await catalog.get_by_slug("sekiro")
    assert game is not None
    assert game.cover_url == "/api/v1/media/covers/x"
    assert game.letsplay_status is LetsPlayStatus.ok
    assert game.letsplay_highlights == ("deflect",)


async def test_daily_processed_slugs_unique_constraint(session: AsyncSession) -> None:
    session.add(DailyProcessedSlug(process_date=date(2026, 9, 7), metacritic_slug="elden-ring"))
    await session.flush()
    session.add(DailyProcessedSlug(process_date=date(2026, 9, 7), metacritic_slug="elden-ring"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_discovery_records_daily_slug_duplicate_flag(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    catalog = GameCatalogRepository(session)
    assert not hasattr(catalog, "record_daily_processed_slug")
    first = await ingestion.record_daily_processed_slug(date(2026, 9, 7), "armored-core")
    second = await ingestion.record_daily_processed_slug(date(2026, 9, 7), "armored-core")
    assert first is InsertOutcome.inserted
    assert second is InsertOutcome.duplicate
    assert await ingestion.is_slug_processed_today(date(2026, 9, 7), "armored-core")
    slugs = await ingestion.list_daily_processed_slugs(date(2026, 9, 7))
    assert slugs == ("armored-core",)


async def test_advisory_xact_lock_exclusive(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await session.commit()
    first = session_factory()
    second = session_factory()
    await first.begin()
    await second.begin()
    try:
        held = await IngestionRepository(first).try_advisory_lock(742001)
        other = await IngestionRepository(second).try_advisory_lock(742001)
        assert held is True
        assert other is False
    finally:
        await first.rollback()
        await second.rollback()
        await first.close()
        await second.close()


async def test_processed_events_unique_event_id_and_idempotency_key(
    session: AsyncSession,
) -> None:
    ingestion = IngestionRepository(session)
    first = await ingestion.insert_processed_event(
        event_id="evt-1",
        idempotency_key="key-1",
        type="game.discovered",
        worker_type="catalog",
        instance_id="a",
    )
    sibling = await ingestion.insert_processed_event(
        event_id="evt-1",
        idempotency_key="key-1",
        type="game.discovered",
        worker_type="reviews",
        instance_id="reviews-1",
    )
    dup_event = await ingestion.insert_processed_event(
        event_id="evt-1",
        idempotency_key="key-other",
        type="game.discovered",
        worker_type="catalog",
        instance_id="b",
    )
    dup_key = await ingestion.insert_processed_event(
        event_id="evt-2",
        idempotency_key="key-1",
        type="game.discovered",
        worker_type="catalog",
        instance_id="c",
    )
    assert first is InsertOutcome.inserted
    assert sibling is InsertOutcome.inserted
    assert dup_event is InsertOutcome.duplicate
    assert dup_key is InsertOutcome.duplicate


async def test_parallel_idempotency_key_returns_duplicate(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await session.commit()

    async def insert_once(event_id: str) -> InsertOutcome:
        async with session_factory() as other:
            async with other.begin():
                return await IngestionRepository(other).insert_processed_event(
                    event_id=event_id,
                    idempotency_key="game.cataloged:run:slug:cataloged",
                    type="game.cataloged",
                    worker_type="catalog",
                    instance_id=event_id,
                )

    outcomes = await asyncio.gather(insert_once("e1"), insert_once("e2"))
    assert sorted(outcomes) == [InsertOutcome.duplicate, InsertOutcome.inserted]


async def test_domain_and_outbox_rollback_together(session: AsyncSession) -> None:
    catalog = GameCatalogRepository(session)
    outbox = OutboxRepository(session)
    with pytest.raises(RuntimeError, match="boom"):
        async with session.begin():
            await catalog.upsert_catalog(_catalog("nightreign", "Nightreign"))
            await outbox.insert(
                OutboxInsert(
                    producer="catalog",
                    idempotency_key="game.cataloged:r:nightreign:cataloged",
                    topic="game.cataloged",
                    partition_key="nightreign",
                    payload={"id": "ce-1", "type": "game.cataloged"},
                )
            )
            raise RuntimeError("boom")
    assert await catalog.get_by_slug("nightreign") is None
    claimed = await OutboxRepository(session).claim("catalog", limit=10)
    assert claimed == ()


async def test_outbox_claim_skips_locked_row(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    outbox = OutboxRepository(session)
    inserted = await outbox.insert(
        OutboxInsert(
            producer="catalog",
            idempotency_key="out-1",
            topic="game.cataloged",
            partition_key="slug",
            payload={"hello": "world"},
        )
    )
    assert inserted.outcome is InsertOutcome.inserted
    await session.commit()

    first = session_factory()
    second = session_factory()
    await first.begin()
    await second.begin()
    try:
        claimed_first = await OutboxRepository(first).claim("catalog", limit=10)
        claimed_second = await OutboxRepository(second).claim("catalog", limit=10)
        assert len(claimed_first) == 1
        assert claimed_first[0].idempotency_key == "out-1"
        assert claimed_second == ()
    finally:
        await first.rollback()
        await second.rollback()
        await first.close()
        await second.close()


async def test_outbox_duplicate_idempotency_is_flag(session: AsyncSession) -> None:
    repo = OutboxRepository(session)
    row = OutboxInsert(
        producer="api",
        idempotency_key="tick:2026-09-07T00",
        topic="ingestion.schedule.tick",
        partition_key="tick",
        payload={"trigger": "manual"},
    )
    first = await repo.insert_schedule_tick(
        producer=row.producer,
        idempotency_key=row.idempotency_key,
        topic=row.topic,
        partition_key=row.partition_key,
        payload=row.payload,
    )
    second = await repo.insert(row)
    assert first.outcome is InsertOutcome.inserted
    assert second.outcome is InsertOutcome.duplicate


async def test_similar_self_insert_rejected_and_replace_is_transactional(
    session: AsyncSession,
) -> None:
    catalog = GameCatalogRepository(session)
    similar = SimilarGamesRepository(session)
    id_a = await catalog.upsert_catalog(_catalog("game-a", "Game A"))
    id_b = await catalog.upsert_catalog(_catalog("game-b", "Game B"))
    await similar.replace_for_game(
        id_a,
        [SimilarNeighbor(similar_game_id=id_b, score=0.9, rank=1, score_vector=0.8)],
    )
    await session.commit()

    from games_intel.db.exceptions import SimilarGameSelfReferenceError

    with pytest.raises(SimilarGameSelfReferenceError):
        async with session.begin():
            await similar.replace_for_game(
                id_a,
                [SimilarNeighbor(similar_game_id=id_a, score=1.0, rank=1)],
            )

    neighbors = await similar.list_for_slug("game-a")
    assert len(neighbors) == 1
    assert neighbors[0].metacritic_slug == "game-b"
    assert neighbors[0].score == 0.9


async def test_similar_replace_all_inline(session: AsyncSession) -> None:
    catalog = GameCatalogRepository(session)
    similar = SimilarGamesRepository(session)
    id_a = await catalog.upsert_catalog(_catalog("alpha", "Alpha"))
    id_b = await catalog.upsert_catalog(_catalog("beta", "Beta"))
    await similar.replace_all(
        {
            id_a: [SimilarNeighbor(similar_game_id=id_b, score=0.5, rank=1)],
            id_b: [SimilarNeighbor(similar_game_id=id_a, score=0.5, rank=1)],
        }
    )
    a_neighbors = await similar.list_for_slug("alpha")
    b_neighbors = await similar.list_for_slug("beta")
    assert a_neighbors[0].metacritic_slug == "beta"
    assert b_neighbors[0].metacritic_slug == "alpha"


async def test_list_games_filter_search_sort(session: AsyncSession) -> None:
    catalog = GameCatalogRepository(session)
    await catalog.upsert_catalog(
        _catalog(
            "low-score",
            "Zebra Quest",
            platforms=(
                PlatformScoreRecord(platform_code="ns2", metascore=70, userscore=Decimal("8.1")),
            ),
        )
    )
    await catalog.upsert_catalog(
        _catalog(
            "high-score",
            "Alpha Strike",
            platforms=(
                PlatformScoreRecord(platform_code="ps5", metascore=95, userscore=Decimal("5.0")),
            ),
        )
    )
    by_score = await catalog.list_games(sort=GameSort.metascore)
    assert [item.metacritic_slug for item in by_score.items] == ["high-score", "low-score"]
    by_title = await catalog.list_games(q="Zebra")
    assert [item.metacritic_slug for item in by_title.items] == ["low-score"]
    by_platform = await catalog.list_games(platform="ps5")
    assert [item.metacritic_slug for item in by_platform.items] == ["high-score"]
    codes = await catalog.list_platform_codes()
    assert codes == ("ns2", "ps5")


async def test_cursor_advances_only_via_explicit_method(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    assert await ingestion.get_cursor(date(2026, 9, 7)) is None
    cursor = await ingestion.advance_cursor(
        date(2026, 9, 7), new_releases_done=True, last_browse_page=0
    )
    assert cursor.new_releases_done is True
    assert cursor.last_browse_page == 0


async def test_cron_and_manual_share_inflight_unique(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    first = await ingestion.create_run(
        process_date=date(2026, 9, 7),
        source="browse",
        page=1,
        limit=20,
        trigger=RunTrigger.cron,
    )
    second = await ingestion.create_run(
        process_date=date(2026, 9, 7),
        source="browse",
        page=1,
        limit=20,
        trigger=RunTrigger.cron,
    )
    manual = await ingestion.create_run(
        process_date=date(2026, 9, 7),
        source="browse",
        page=1,
        limit=20,
        trigger=RunTrigger.manual,
    )
    assert first.outcome is InsertOutcome.inserted
    assert second.outcome is InsertOutcome.duplicate
    assert second.id == first.id
    assert manual.outcome is InsertOutcome.duplicate
    assert manual.id == first.id


async def test_item_lock_and_attempt_count(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    run = await ingestion.create_run(
        process_date=date(2026, 9, 7),
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.cron,
    )
    assert isinstance(run.id, UUID)
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="elden-ring",
        process_date=date(2026, 9, 7),
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.pending,
    )
    locked = await ingestion.lock_item(
        run.id,
        "elden-ring",
        IngestionStage.cataloged,
        lease_seconds=120,
    )
    assert locked is not None
    assert locked.status is IngestionItemStatus.pending
    count = await ingestion.increment_attempt(locked.id)
    assert count == 1


async def test_heartbeat_upsert_by_instance(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    observed = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)
    await ingestion.upsert_heartbeat(
        worker_type="catalog",
        instance_id="replica-a",
        status="running",
        current_subject="elden-ring",
        processed_ok=3,
        processed_failed=0,
        lag_hint=1,
        observed_at=observed,
    )
    await ingestion.upsert_heartbeat(
        worker_type="catalog",
        instance_id="replica-b",
        status="idle",
        current_subject=None,
        processed_ok=1,
        processed_failed=0,
        lag_hint=None,
        observed_at=observed,
    )
    await ingestion.upsert_heartbeat(
        worker_type="catalog",
        instance_id="replica-a",
        status="idle",
        current_subject=None,
        processed_ok=4,
        processed_failed=0,
        lag_hint=0,
        observed_at=observed,
    )
    beats = await ingestion.list_heartbeats()
    assert len(beats) == 2
    replica_a = next(item for item in beats if item.instance_id == "replica-a")
    assert replica_a.processed_ok == 4
    assert replica_a.status == "idle"


async def test_monitor_aggregates(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    process_date = date(2026, 9, 7)
    run = await ingestion.create_run(
        process_date=process_date,
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.cron,
    )
    assert isinstance(run.id, UUID)
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="g1",
        process_date=process_date,
        stage=IngestionStage.discovered,
        status=IngestionItemStatus.completed,
    )
    snapshot = await ingestion.monitor_aggregates(process_date)
    assert len(snapshot.runs) == 1
    assert snapshot.stage_counts[0].stage == "discovered"
    assert snapshot.stage_counts[0].count == 1
    assert snapshot.parse_error_count == 0
    assert len(snapshot.items) == 1
    assert snapshot.items[0].metacritic_slug == "g1"
    assert snapshot.items[0].title is None


async def test_monitor_aggregates_failed_degraded_and_parse_errors(
    session: AsyncSession,
) -> None:
    ingestion = IngestionRepository(session)
    process_date = date(2026, 9, 7)
    run = await ingestion.create_run(
        process_date=process_date,
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.cron,
    )
    assert isinstance(run.id, UUID)
    catalog = GameCatalogRepository(session)
    await catalog.upsert_catalog(_catalog("ok-game", "OK Game"))
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="ok-game",
        process_date=process_date,
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.completed,
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="failed-game",
        process_date=process_date,
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.failed,
        error_type="NotFoundError",
        error_message="404",
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="degraded-game",
        process_date=process_date,
        stage=IngestionStage.letsplay,
        status=IngestionItemStatus.degraded,
        error_type="QuotaError",
        error_message="quota",
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="parse-game",
        process_date=process_date,
        stage=IngestionStage.discovered,
        status=IngestionItemStatus.failed,
        error_type="ParseError",
        error_message="markers missing",
    )
    snapshot = await ingestion.monitor_aggregates(process_date)
    by_key = {(row.stage, row.status): row.count for row in snapshot.stage_counts}
    assert by_key[("cataloged", "completed")] == 1
    assert by_key[("cataloged", "failed")] == 1
    assert by_key[("letsplay", "degraded")] == 1
    assert by_key[("discovered", "failed")] == 1
    assert snapshot.parse_error_count == 1
    titles = {row.metacritic_slug: row.title for row in snapshot.items}
    assert titles["ok-game"] == "OK Game"
    assert titles["failed-game"] is None


async def test_ensure_stub_does_not_overwrite_catalog(session: AsyncSession) -> None:
    catalog = GameCatalogRepository(session)
    await catalog.upsert_catalog(_catalog("bloodborne", "Bloodborne", cover_url="/covers/bb"))
    _id, outcome = await catalog.ensure_game_stub(metacritic_slug="bloodborne", title="Wrong Title")
    assert outcome is InsertOutcome.duplicate
    game = await catalog.get_by_slug("bloodborne")
    assert game is not None
    assert game.title == "Bloodborne"
    assert game.cover_url == "/covers/bb"


async def test_processed_events_raw_unique(session: AsyncSession) -> None:
    session.add(
        ProcessedEvent(
            event_id="raw-1",
            idempotency_key="ik-1",
            type="game.discovered",
            worker_type="discovery",
            instance_id="i",
        )
    )
    await session.flush()
    session.add(
        ProcessedEvent(
            event_id="raw-1",
            idempotency_key="ik-2",
            type="game.discovered",
            worker_type="discovery",
            instance_id="i",
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_processed_events_same_event_allowed_for_sibling_workers(
    session: AsyncSession,
) -> None:
    session.add(
        ProcessedEvent(
            event_id="raw-shared",
            idempotency_key="ik-shared",
            type="game.discovered",
            worker_type="catalog",
            instance_id="catalog-1",
        )
    )
    await session.flush()
    session.add(
        ProcessedEvent(
            event_id="raw-shared",
            idempotency_key="ik-shared",
            type="game.discovered",
            worker_type="reviews",
            instance_id="reviews-1",
        )
    )
    await session.flush()


async def test_page_cache_roundtrip_and_ttl(session: AsyncSession) -> None:
    repo = PageCacheRepository(session)
    fetched = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    await repo.put(
        url_hash="abc",
        body="<html>ok</html>",
        http_status=200,
        content_type="text/html",
        fetched_at=fetched,
    )
    hit = await repo.get_fresh(
        "abc",
        ttl_seconds=3600,
        now=fetched + timedelta(seconds=10),
    )
    assert hit is not None
    assert hit.body == "<html>ok</html>"
    stale = await repo.get_fresh(
        "abc",
        ttl_seconds=5,
        now=fetched + timedelta(seconds=10),
    )
    assert stale is None
    missing = await repo.get("missing")
    assert missing is None


async def test_adapter_health_upsert(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    first = await ingestion.upsert_adapter_health(
        adapter_name="metacritic",
        circuit_state="open",
        parse_error_streak=3,
        opened_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        last_parse_error_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    assert first.circuit_state == "open"
    second = await ingestion.upsert_adapter_health(
        adapter_name="metacritic",
        circuit_state="closed",
        parse_error_streak=0,
        opened_at=None,
        last_parse_error_at=first.last_parse_error_at,
    )
    assert second.circuit_state == "closed"
    loaded = await ingestion.get_adapter_health("metacritic")
    assert loaded is not None
    assert loaded.circuit_state == "closed"
