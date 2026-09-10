from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.in_process import InProcessMetacriticAdapter
from games_intel.contracts import RunRequested, build_cloud_event
from games_intel.contracts.adapters import CanaryParseResult, GameListing, GameListingItem
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.payloads import RunSource
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import IngestionRunStatus, InsertOutcome, RunTrigger
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.exceptions import TransientError
from games_intel.kafka.serialization import encode_cloud_event
from games_intel.kafka.source import worker_source
from games_intel.kafka.testing import FakeBroker, FakeConsumer, FakeProducer
from games_intel.kafka.types import IncomingRecord
from games_intel.settings import Settings
from games_intel.workers.discovery.handler import DiscoveryHandler

PROCESS_DATE = date(2026, 9, 8)
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-0000000000aa")
CANARY_SLUG = "elden-ring"
DISCOVERY_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "games_intel" / "workers" / "discovery"
)


def _settings() -> Settings:
    return Settings()


def _item(index: int, *, slug: str | None = None) -> GameListingItem:
    name = slug or f"game-{index:02d}"
    return GameListingItem(
        slug=name,
        title=f"Game {index:02d}",
        listing_url=HttpUrl(f"https://www.metacritic.com/game/{name}/"),
        position=index,
    )


def _listing(
    count: int = 20, *, source: RunSource = "new_releases", page: int | None = None
) -> GameListing:
    return GameListing(
        items=[_item(i) for i in range(count)],
        source=source,
        page=page,
    )


def _canary_ok() -> CanaryParseResult:
    return CanaryParseResult(ok=True, error_code=None)


def _port(
    *,
    listing: GameListing | None = None,
    browse: dict[int, GameListing] | None = None,
    canary: CanaryParseResult | None = None,
    errors: dict[str, MetacriticAdapterError] | None = None,
) -> InProcessMetacriticAdapter:
    return InProcessMetacriticAdapter(
        listings={"new_releases": listing} if listing is not None else None,
        browse=browse,
        canaries={CANARY_SLUG: canary or _canary_ok()},
        errors=errors,
    )


def _run_event(
    *, event_id: str, source: RunSource = "new_releases", page: int | None = None
) -> CloudEvent[Any]:
    settings = _settings()
    data = RunRequested(
        run_id=RUN_ID,
        process_date=PROCESS_DATE,
        source=source,
        page=page,
        limit=settings.scheduler.default_limit,
        trigger="cron",
    )
    return build_cloud_event(
        settings,
        "run_requested",
        source=worker_source(settings, "scheduler"),
        subject=str(RUN_ID),
        data=data,
        stage="scheduled",
        run_id=RUN_ID,
        event_id=event_id,
        occurred_at=NOW,
    )


def _record(event: CloudEvent[Any]) -> IncomingRecord:
    settings = _settings()
    return IncomingRecord(
        topic=settings.event_name("run_requested"),
        partition=0,
        offset=0,
        key=str(RUN_ID),
        value=encode_cloud_event(event),
    )


async def _no_sleep(_delay: float) -> None:
    return None


def _see_committed(session: AsyncSession) -> None:
    session.expire_all()


async def _seed_run(
    session: AsyncSession, *, source: str = "new_releases", page: int | None = None
) -> None:
    await IngestionRepository(session).create_run(
        process_date=PROCESS_DATE,
        source=source,
        page=page,
        limit=20,
        trigger=RunTrigger.cron,
        run_id=RUN_ID,
    )
    await session.commit()
    session.expire_all()


def _loop(
    session_factory: async_sessionmaker[AsyncSession],
    handler: DiscoveryHandler,
) -> tuple[DaemonLoop, FakeBroker, FakeConsumer]:
    settings = _settings()
    retry = settings.retry.model_copy(
        update={"max_attempts": 3, "backoff_base_seconds": 0, "jitter_ratio": 0}
    )
    settings = settings.model_copy(update={"retry": retry})
    broker = FakeBroker()
    consumer = FakeConsumer(broker, (settings.event_name("run_requested"),))
    producer = FakeProducer(broker)
    loop = DaemonLoop(
        settings,
        DaemonConfig(
            worker_type="discovery",
            instance_id="discovery-1",
            stage_name=settings.discovery.stage_name,
            subscribe_event_key="run_requested",
        ),
        consumer=consumer,
        producer=producer,
        session_factory=session_factory,
        handler=handler,
        sleep=_no_sleep,
    )
    return loop, broker, consumer


async def test_twenty_dto_twenty_events_seen_filtered(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    await IngestionRepository(session).record_daily_processed_slug(PROCESS_DATE, "game-00")
    await session.commit()
    port = _port(listing=_listing(20))
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    await loop.process_record(_record(_run_event(event_id="run-20")))
    _see_committed(session)
    rows = await OutboxRepository(session).claim("discovery", limit=50)
    assert len(rows) == 19
    slugs = [row.payload["data"]["game"]["metacritic_slug"] for row in rows]
    assert len(slugs) == 19
    assert "game-00" not in slugs
    assert "game-01" in slugs
    assert {row.partition_key for row in rows} == set(slugs)
    daily = await IngestionRepository(session).list_daily_processed_slugs(PROCESS_DATE)
    assert daily == ("game-00",)
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.completed
    assert run.discovered_count == 19
    cursor = await IngestionRepository(session).get_cursor(PROCESS_DATE)
    assert cursor is not None
    assert cursor.new_releases_done is True


async def test_twenty_unseen_emits_one_listed_event_each(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    port = _port(listing=_listing(20))
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    await loop.process_record(_record(_run_event(event_id="run-all-new")))
    _see_committed(session)
    rows = await OutboxRepository(session).claim("discovery", limit=50)
    assert len(rows) == 20
    assert {row.payload["type"] for row in rows} == {_settings().event_name("game_listed")}
    games = [row.payload["data"]["game"] for row in rows]
    assert len(games) == 20
    assert sorted(game["position"] for game in games) == list(range(20))
    daily = await IngestionRepository(session).list_daily_processed_slugs(PROCESS_DATE)
    assert daily == ()


async def test_browse_keeps_full_page_not_capped_at_twenty(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session, source="browse", page=1)
    port = _port(browse={1: _listing(24, source="browse", page=1)})
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    await loop.process_record(
        _record(_run_event(event_id="run-browse-24", source="browse", page=1))
    )
    _see_committed(session)
    rows = await OutboxRepository(session).claim("discovery", limit=50)
    games = [row.payload["data"]["game"] for row in rows]
    assert len(games) == 24
    browse_calls = [call for call in port.calls if call[0] == "list_browse_page"]
    assert browse_calls[0][1].limit == _settings().discovery.browse_list_limit


async def test_parse_error_does_not_move_cursor_or_emit(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    await IngestionRepository(session).advance_cursor(
        PROCESS_DATE, new_releases_done=False, last_browse_page=None
    )
    await session.commit()
    port = _port(
        listing=_listing(20),
        errors={"list_new_releases": MetacriticAdapterError("parse_error", "markers missing")},
    )
    handler = DiscoveryHandler(_settings(), port)
    loop, broker, consumer = _loop(session_factory, handler)
    record = _record(_run_event(event_id="run-parse"))
    await loop.process_record(record)
    _see_committed(session)
    cursor = await IngestionRepository(session).get_cursor(PROCESS_DATE)
    assert cursor is not None
    assert cursor.new_releases_done is False
    assert await OutboxRepository(session).claim("discovery", limit=10) == ()
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.failed
    assert consumer.committed[(record.topic, 0)] == 1
    dlq = broker.topics[_settings().event_name("dlq")]
    assert len(dlq) == 1


async def test_listing_500_exhausts_retries_run_failed_cursor_stands(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    await IngestionRepository(session).advance_cursor(
        PROCESS_DATE, new_releases_done=False, last_browse_page=None
    )
    await session.commit()
    port = _port(
        listing=_listing(20),
        errors={"list_new_releases": MetacriticAdapterError("unavailable", "HTTP 500")},
    )
    handler = DiscoveryHandler(_settings(), port)
    loop, _, consumer = _loop(session_factory, handler)
    record = _record(_run_event(event_id="run-listing-500"))
    await loop.process_record(record)
    list_calls = [call for call in port.calls if call[0] == "list_new_releases"]
    assert len(list_calls) == 3
    _see_committed(session)
    cursor = await IngestionRepository(session).get_cursor(PROCESS_DATE)
    assert cursor is not None
    assert cursor.new_releases_done is False
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.failed
    assert run.discovered_count == 0
    assert consumer.committed[(record.topic, 0)] == 1
    assert await OutboxRepository(session).claim("discovery", limit=10) == ()


async def test_circuit_open_retries_cursor_unchanged(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    await IngestionRepository(session).advance_cursor(
        PROCESS_DATE, new_releases_done=False, last_browse_page=None
    )
    await session.commit()
    port = _port(
        listing=_listing(20),
        errors={"list_new_releases": MetacriticAdapterError("circuit_open", "open")},
    )
    handler = DiscoveryHandler(_settings(), port)
    loop, _, consumer = _loop(session_factory, handler)
    record = _record(_run_event(event_id="run-circuit"))
    await loop.process_record(record)
    list_calls = [call for call in port.calls if call[0] == "list_new_releases"]
    assert len(list_calls) == 3
    _see_committed(session)
    cursor = await IngestionRepository(session).get_cursor(PROCESS_DATE)
    assert cursor is not None
    assert cursor.new_releases_done is False
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.failed
    assert consumer.committed[(record.topic, 0)] == 1
    assert await OutboxRepository(session).claim("discovery", limit=10) == ()


async def test_canary_slug_not_written_to_daily_slugs(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    port = _port(listing=_listing(5))
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    await loop.process_record(_record(_run_event(event_id="run-canary")))
    daily = await IngestionRepository(session).list_daily_processed_slugs(PROCESS_DATE)
    assert CANARY_SLUG not in daily
    canary_calls = [call for call in port.calls if call[0] == "canary_parse"]
    assert len(canary_calls) == 1


async def test_canary_fail_skips_listing(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    port = _port(
        listing=_listing(5),
        canary=CanaryParseResult(ok=False, error_code="parse_error"),
    )
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    await loop.process_record(_record(_run_event(event_id="run-canary-fail")))
    _see_committed(session)
    assert [call[0] for call in port.calls] == ["canary_parse"]
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.failed
    assert await IngestionRepository(session).get_cursor(PROCESS_DATE) is None
    assert await OutboxRepository(session).claim("discovery", limit=10) == ()


async def test_empty_and_all_seen_advance_cursor(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session, source="browse", page=1)
    listing = _listing(3, source="browse", page=1)
    for item in listing.items:
        await IngestionRepository(session).record_daily_processed_slug(PROCESS_DATE, item.slug)
    await session.commit()
    port = _port(browse={1: listing})
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    event = _run_event(event_id="run-seen", source="browse", page=1)
    await loop.process_record(_record(event))
    _see_committed(session)
    cursor = await IngestionRepository(session).get_cursor(PROCESS_DATE)
    assert cursor is not None
    assert cursor.last_browse_page == 1
    assert cursor.new_releases_done is True
    assert await OutboxRepository(session).claim("discovery", limit=10) == ()
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.completed
    assert run.discovered_count == 0


async def test_empty_browse_listing_fails_without_advancing_cursor(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session, source="browse", page=1)
    port = _port(browse={1: GameListing(items=[], source="browse", page=1)})
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    event = _run_event(event_id="run-empty-browse", source="browse", page=1)
    await loop.process_record(_record(event))
    _see_committed(session)
    assert await IngestionRepository(session).get_cursor(PROCESS_DATE) is None
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.failed
    assert await OutboxRepository(session).claim("discovery", limit=10) == ()


async def test_empty_listing_advances_cursor(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    port = _port(listing=GameListing(items=[], source="new_releases", page=None))
    handler = DiscoveryHandler(_settings(), port)
    loop, _, _ = _loop(session_factory, handler)
    await loop.process_record(_record(_run_event(event_id="run-empty")))
    _see_committed(session)
    cursor = await IngestionRepository(session).get_cursor(PROCESS_DATE)
    assert cursor is not None
    assert cursor.new_releases_done is True
    assert await OutboxRepository(session).claim("discovery", limit=10) == ()


async def test_idempotent_replay_does_not_duplicate_discovered(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    port = _port(listing=_listing(4))
    handler = DiscoveryHandler(_settings(), port)
    loop, _, consumer = _loop(session_factory, handler)
    event = _run_event(event_id="run-idem")
    await loop.process_record(_record(event))
    second = IncomingRecord(
        topic=_settings().event_name("run_requested"),
        partition=0,
        offset=1,
        key=str(RUN_ID),
        value=encode_cloud_event(event),
    )
    await loop.process_record(second)
    _see_committed(session)
    rows = await OutboxRepository(session).claim("discovery", limit=20)
    assert len(rows) == 4
    slugs = {row.payload["data"]["game"]["metacritic_slug"] for row in rows}
    assert slugs == {f"game-{i:02d}" for i in range(4)}
    list_calls = [call for call in port.calls if call[0] == "list_new_releases"]
    assert len(list_calls) == 1
    assert consumer.committed[(second.topic, 0)] == 2


async def test_crash_before_persist_retries_listing(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    port = _port(listing=_listing(2))
    handler = DiscoveryHandler(_settings(), port)
    loop, _, consumer = _loop(session_factory, handler)
    calls = {"n": 0}
    original = GameCatalogRepository.ensure_game_stub

    async def boom(self: GameCatalogRepository, **kwargs: object) -> tuple[UUID, InsertOutcome]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise TransientError("crash before persist")
        return await original(self, **kwargs)  # type: ignore[arg-type]

    record = _record(_run_event(event_id="run-crash"))
    with patch.object(GameCatalogRepository, "ensure_game_stub", boom):
        await loop.process_record(record)
    _see_committed(session)
    list_calls = [call for call in port.calls if call[0] == "list_new_releases"]
    assert len(list_calls) >= 2
    games = await GameCatalogRepository(session).get_by_slug("game-00")
    assert games is not None
    assert consumer.committed[(record.topic, 0)] == 1
    rows = await OutboxRepository(session).claim("discovery", limit=10)
    assert len(rows) == 2
    slugs = {row.payload["data"]["game"]["metacritic_slug"] for row in rows}
    assert slugs == {"game-00", "game-01"}


def test_discovery_does_not_import_catalog_worker() -> None:
    for path in DISCOVERY_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "workers.catalog" not in node.module
                assert "langchain" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "langchain" not in alias.name
