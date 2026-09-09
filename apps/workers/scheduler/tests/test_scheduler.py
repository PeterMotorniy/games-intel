from __future__ import annotations

import ast
import asyncio
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.contracts import ScheduleTick, SimilarityRecomputeRequested, build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.db.engine import is_database_ready
from games_intel.db.records import IngestionCursorRecord
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import IngestionRunStatus, InsertOutcome, RunTrigger
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings
from games_intel.workers.scheduler.clock import process_date_for
from games_intel.workers.scheduler.handler import SchedulerHandler
from games_intel.workers.scheduler.recompute import (
    enqueue_full_recompute,
    full_recompute_idempotency_key,
)
from games_intel.workers.scheduler.source import decide_source_and_page
from games_intel.workers.scheduler.ticks import enqueue_schedule_tick

PROCESS_DATE = date(2026, 9, 8)
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
SCHEDULER_SRC = (
    Path(__file__).resolve().parents[1] / "src" / "games_intel" / "workers" / "scheduler"
)


def _settings() -> Settings:
    return Settings()


def _tick(*, event_id: str, trigger: Literal["cron", "manual"] = "cron") -> CloudEvent[Any]:
    settings = _settings()
    data = ScheduleTick(trigger=trigger, requested_at=NOW, process_date=PROCESS_DATE)
    return build_cloud_event(
        settings,
        "schedule_tick",
        source=worker_source(settings, "api"),
        subject=PROCESS_DATE.isoformat(),
        data=data,
        stage="tick",
        event_id=event_id,
        occurred_at=NOW,
        idempotency_key=f"tick:{event_id}",
    )


async def test_second_tick_opens_next_page_not_duplicate(session: AsyncSession) -> None:
    handler = SchedulerHandler(_settings())
    first = _tick(event_id="tick-1")
    second = _tick(event_id="tick-2")
    await handler.handle(first, session)
    await handler.handle(second, session)
    runs = await IngestionRepository(session).list_runs_for_date(PROCESS_DATE)
    assert {(run.source, run.page) for run in runs} == {
        (_settings().scheduler.new_releases_source, None),
        (_settings().scheduler.browse_source, 1),
    }
    assert {run.trigger for run in runs} == {RunTrigger.cron}
    claimed = await OutboxRepository(session).claim("scheduler", limit=10)
    topics = {row.payload["data"]["source"] for row in claimed}
    assert topics == {"new_releases", "browse"}
    browse = next(row for row in claimed if row.payload["data"]["source"] == "browse")
    assert browse.payload["data"]["page"] == 1


async def test_first_tick_of_day_is_new_releases(session: AsyncSession) -> None:
    handler = SchedulerHandler(_settings())
    await handler.handle(_tick(event_id="tick-nr"), session)
    runs = await IngestionRepository(session).list_runs_for_date(PROCESS_DATE)
    assert runs[0].source == "new_releases"
    assert runs[0].page is None
    assert runs[0].limit == _settings().scheduler.default_limit


async def test_after_new_releases_done_browse_page_one(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    await ingestion.advance_cursor(PROCESS_DATE, new_releases_done=True, last_browse_page=None)
    handler = SchedulerHandler(_settings())
    await handler.handle(_tick(event_id="tick-browse"), session)
    runs = await IngestionRepository(session).list_runs_for_date(PROCESS_DATE)
    assert len(runs) == 1
    assert runs[0].source == _settings().scheduler.browse_source
    assert runs[0].page == 1


async def test_browse_uses_last_page_plus_one(session: AsyncSession) -> None:
    await IngestionRepository(session).advance_cursor(
        PROCESS_DATE, new_releases_done=True, last_browse_page=3
    )
    source, page = decide_source_and_page(
        await IngestionRepository(session).get_cursor(PROCESS_DATE),
        _settings(),
    )
    assert source == "browse"
    assert page == 4


def test_inflight_new_releases_opens_browse_page_one() -> None:
    from types import SimpleNamespace

    source, page = decide_source_and_page(
        None,
        _settings(),
        (SimpleNamespace(source="new_releases", page=None, status=IngestionRunStatus.requested),),
    )
    assert source == "browse"
    assert page == 1


def test_inflight_browse_page_opens_next() -> None:
    from types import SimpleNamespace

    cursor = IngestionCursorRecord(
        process_date=PROCESS_DATE,
        new_releases_done=True,
        last_browse_page=3,
        updated_at=NOW,
    )
    source, page = decide_source_and_page(
        cursor,
        _settings(),
        (SimpleNamespace(source="browse", page=4, status=IngestionRunStatus.running),),
    )
    assert source == "browse"
    assert page == 5


def test_failed_run_does_not_reserve_page() -> None:
    from types import SimpleNamespace

    cursor = IngestionCursorRecord(
        process_date=PROCESS_DATE,
        new_releases_done=True,
        last_browse_page=3,
        updated_at=NOW,
    )
    source, page = decide_source_and_page(
        cursor,
        _settings(),
        (SimpleNamespace(source="browse", page=4, status=IngestionRunStatus.failed),),
    )
    assert source == "browse"
    assert page == 4


async def test_manual_then_cron_share_the_same_next_page(session: AsyncSession) -> None:
    handler = SchedulerHandler(_settings())
    await handler.handle(_tick(event_id="m1", trigger="manual"), session)
    await handler.handle(_tick(event_id="c1", trigger="cron"), session)
    runs = await IngestionRepository(session).list_runs_for_date(PROCESS_DATE)
    assert {(run.source, run.page, run.trigger) for run in runs} == {
        ("new_releases", None, RunTrigger.manual),
        ("browse", 1, RunTrigger.cron),
    }


async def test_failed_browse_page_is_retried_before_advancing(session: AsyncSession) -> None:
    ingestion = IngestionRepository(session)
    await ingestion.advance_cursor(PROCESS_DATE, new_releases_done=True, last_browse_page=2)
    created = await ingestion.create_run(
        process_date=PROCESS_DATE,
        source="browse",
        page=3,
        limit=20,
        trigger=RunTrigger.cron,
    )
    assert created.id is not None
    await ingestion.update_run(created.id, status=IngestionRunStatus.failed)
    handler = SchedulerHandler(_settings())
    await handler.handle(_tick(event_id="retry-failed"), session)
    runs = await ingestion.list_runs_for_date(PROCESS_DATE)
    browse_pages = [run.page for run in runs if run.source == "browse"]
    assert browse_pages == [3, 3]


async def test_two_handlers_without_lock_claim_next_page(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await session.commit()
    handler_a = SchedulerHandler(_settings(), use_lock=False)
    handler_b = SchedulerHandler(_settings(), use_lock=False)

    async def run_one(event_id: str, handler: SchedulerHandler) -> None:
        async with session_factory() as other:
            async with other.begin():
                await handler.handle(_tick(event_id=event_id), other)

    await asyncio.gather(run_one("a", handler_a), run_one("b", handler_b))
    async with session_factory() as check:
        runs = await IngestionRepository(check).list_runs_for_date(PROCESS_DATE)
    assert sorted((run.source, run.page) for run in runs) == [
        ("browse", 1),
        ("new_releases", None),
    ]
    assert handler_a.runs_created + handler_b.runs_created == 2


async def test_two_handlers_with_lock_one_run(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await session.commit()
    handler_a = SchedulerHandler(_settings(), use_lock=True)
    handler_b = SchedulerHandler(_settings(), use_lock=True)

    async def run_one(event_id: str, handler: SchedulerHandler) -> None:
        async with session_factory() as other:
            async with other.begin():
                await handler.handle(_tick(event_id=event_id), other)

    await asyncio.gather(run_one("lock-a", handler_a), run_one("lock-b", handler_b))
    async with session_factory() as check:
        runs = await IngestionRepository(check).list_runs_for_date(PROCESS_DATE)
    assert len(runs) == 1
    assert handler_a.runs_created + handler_b.runs_created == 1
    assert handler_a.lock_attempts + handler_b.lock_attempts == 2
    assert handler_a.lock_acquired + handler_b.lock_acquired >= 1


async def test_recompute_uses_event_type_from_settings_not_worker_name(
    session: AsyncSession,
) -> None:
    settings = _settings()
    custom = settings.model_copy(
        update={
            "kafka": settings.kafka.model_copy(
                update={
                    "events": settings.kafka.events.model_copy(
                        update={"similarity_recompute": "custom.recompute.v1"}
                    )
                }
            )
        }
    )
    outcome = await enqueue_full_recompute(session, custom, when=NOW)
    assert outcome is InsertOutcome.inserted
    rows = await OutboxRepository(session).claim("scheduler", limit=10)
    assert len(rows) == 1
    assert rows[0].topic == "custom.recompute.v1"
    assert rows[0].payload["type"] == "custom.recompute.v1"
    data = SimilarityRecomputeRequested.model_validate(rows[0].payload["data"])
    assert data.scope == "all"
    assert data.reason == "schedule"
    assert rows[0].idempotency_key == full_recompute_idempotency_key(custom, NOW)
    assert "SimilarityWorker" not in rows[0].idempotency_key
    second = await enqueue_full_recompute(session, custom, when=NOW)
    assert second is InsertOutcome.duplicate


async def test_process_date_uses_configured_timezone() -> None:
    settings = _settings().model_copy(
        update={"app": _settings().app.model_copy(update={"process_timezone": "America/New_York"})}
    )
    # 2026-09-08 02:30 UTC is still 2026-09-07 in New York (EDT, UTC-4).
    when = datetime(2026, 9, 8, 2, 30, tzinfo=UTC)
    assert process_date_for(settings, when) == date(2026, 9, 7)


async def test_database_down_is_not_ready(engine: AsyncEngine) -> None:
    assert await is_database_ready(engine) is True
    from games_intel.db.engine import create_engine as make_engine

    broken = make_engine(
        Settings(),
        url="postgresql+asyncpg://games:bad@127.0.0.1:1/missing",
    )
    try:
        assert await is_database_ready(broken) is False
    finally:
        await broken.dispose()


def test_scheduler_sources_have_no_site_or_llm_imports() -> None:
    forbidden = ("langchain", "metacritic", "playwright", "httpx")
    for path in SCHEDULER_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                lowered = name.lower()
                for token in forbidden:
                    assert token not in lowered, f"{path} imports {name}"


def test_interval_comes_from_settings_not_literal() -> None:
    handler_src = (SCHEDULER_SRC / "handler.py").read_text(encoding="utf-8")
    runtime_src = (SCHEDULER_SRC / "runtime.py").read_text(encoding="utf-8")
    assert "3600" not in handler_src
    assert "tick_interval_seconds" in runtime_src


async def test_in_process_tick_dedup_window(session: AsyncSession) -> None:
    settings = _settings()
    first = await enqueue_schedule_tick(session, settings, trigger="cron", when=NOW)
    second = await enqueue_schedule_tick(session, settings, trigger="cron", when=NOW)
    assert first is InsertOutcome.inserted
    assert second is InsertOutcome.duplicate


def test_cron_matches_hourly_and_fifteenth_minute() -> None:
    from games_intel.workers.scheduler.cron import cron_matches

    noon = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    fifteen = datetime(2026, 9, 8, 12, 15, tzinfo=UTC)
    assert cron_matches("0 * * * *", noon) is True
    assert cron_matches("0 * * * *", fifteen) is False
    assert cron_matches("15 * * * *", fifteen) is True
    assert cron_matches("15 * * * *", noon) is False


def test_cron_minute_gate_fires_once_per_minute() -> None:
    from games_intel.workers.scheduler.cron import CronMinuteGate

    gate = CronMinuteGate()
    noon = datetime(2026, 9, 8, 12, 0, 10, tzinfo=UTC)
    later_same_minute = datetime(2026, 9, 8, 12, 0, 50, tzinfo=UTC)
    next_hour = datetime(2026, 9, 8, 13, 0, 1, tzinfo=UTC)
    assert gate.due("0 * * * *", noon) is True
    assert gate.due("0 * * * *", later_same_minute) is False
    assert gate.due("0 * * * *", next_hour) is True


async def test_external_tick_requires_external_source(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    import pytest

    from games_intel.kafka.testing import FakeBroker, FakeProducer
    from games_intel.workers.scheduler.external_tick import ExternalTickRuntime

    base = _settings()
    settings = base.model_copy(
        update={"scheduler": base.scheduler.model_copy(update={"tick_source": "in_process"})}
    )
    broker = FakeBroker()
    runtime = ExternalTickRuntime(
        settings,
        session_factory=session_factory,
        engine=engine,
        producer=FakeProducer(broker),
    )
    with pytest.raises(RuntimeError, match="tick_source must be external"):
        await runtime.run(asyncio.Event())


async def test_external_tick_enqueues_cron_when_due(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    from games_intel.kafka.testing import FakeBroker, FakeProducer
    from games_intel.workers.scheduler.external_tick import ExternalTickRuntime

    await session.commit()
    settings = _settings()
    assert settings.scheduler.tick_source == "external"
    stop = asyncio.Event()

    async def sleep_and_stop(_delay: float) -> None:
        stop.set()

    broker = FakeBroker()
    runtime = ExternalTickRuntime(
        settings,
        session_factory=session_factory,
        engine=engine,
        producer=FakeProducer(broker),
        sleep=sleep_and_stop,
        clock=lambda: NOW,
    )
    await runtime.run(stop)
    assert runtime.ticks_enqueued == 1
    topic = settings.event_name(settings.scheduler.subscribe_event)
    assert len(broker.topics[topic]) == 1
    payload = broker.topics[topic][0]
    assert payload.key == PROCESS_DATE.isoformat()
