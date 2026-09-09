from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.api.app import ReadyFn, create_app
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage, RunTrigger
from games_intel.kafka.envelope import parse_cloud_event
from games_intel.kafka.serialization import encode_payload
from games_intel.settings import Settings
from games_intel.settings.config import MediaSettings
from games_intel.workers.scheduler.handler import SchedulerHandler

PROBLEM_JSON = "application/problem+json"
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
PROCESS_DATE = date(2026, 9, 8)


def _settings(tmp_path: Path, **monitor: object) -> Settings:
    base = Settings()
    media = MediaSettings(
        covers_dir=str(tmp_path),
        covers_url_prefix=base.media.covers_url_prefix,
        covers_cache_control=base.media.covers_cache_control,
    )
    updates: dict[str, object] = {"media": media}
    if monitor:
        updates["monitor"] = base.monitor.model_copy(update=monitor)
    return base.model_copy(update=updates)


async def _always_ready() -> bool:
    return True


async def _never_ready() -> bool:
    return False


def _app(
    settings: Settings,
    *,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    postgres_ready: ReadyFn | None = None,
    clock: object = None,
) -> FastAPI:
    return create_app(
        settings,
        engine=engine,
        session_factory=session_factory,
        postgres_ready=postgres_ready if postgres_ready is not None else _never_ready,
        kafka_ready=_never_ready,
        clock=clock if callable(clock) else None,
    )


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def monitor_client(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> AsyncIterator[httpx.AsyncClient]:
    settings = _settings(tmp_path, sse_poll_seconds=0.2)
    app = _app(
        settings,
        engine=engine,
        session_factory=session_factory,
        postgres_ready=_always_ready,
        clock=lambda: NOW,
    )
    async for client in _client(app):
        yield client


def test_openapi_contains_monitor_and_runs() -> None:
    schema = create_app(Settings(), postgres_ready=_never_ready, kafka_ready=_never_ready).openapi()
    paths = schema["paths"]
    assert "/api/v1/monitor" in paths
    assert "/api/v1/monitor/stream" in paths
    assert "/api/v1/runs" in paths
    assert paths["/api/v1/monitor"]["get"]
    assert paths["/api/v1/monitor/stream"]["get"]
    assert paths["/api/v1/runs"]["post"]
    models = schema["components"]["schemas"]
    assert "MonitorSnapshot" in models
    assert "RunAcceptedResponse" in models
    assert "WorkerHeartbeatRead" in models
    snapshot = models["MonitorSnapshot"]["properties"]
    assert "workers" in snapshot
    assert "scrape" in snapshot
    assert "counts" in snapshot
    assert "items" in snapshot
    assert "MonitorItemRead" in models


async def test_two_catalog_replicas_are_two_rows(
    monitor_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    ingestion = IngestionRepository(session)
    await ingestion.upsert_heartbeat(
        worker_type="catalog",
        instance_id="catalog-a",
        status="running",
        current_subject="elden-ring",
        processed_ok=3,
        processed_failed=0,
        lag_hint=1,
        observed_at=NOW,
    )
    await ingestion.upsert_heartbeat(
        worker_type="catalog",
        instance_id="catalog-b",
        status="idle",
        current_subject=None,
        processed_ok=1,
        processed_failed=0,
        lag_hint=None,
        observed_at=NOW,
    )
    await session.commit()
    response = await monitor_client.get("/api/v1/monitor")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    catalog = [row for row in body["workers"] if row["worker_type"] == "catalog"]
    assert {row["instance_id"] for row in catalog} == {"catalog-a", "catalog-b"}
    replica_a = next(row for row in catalog if row["instance_id"] == "catalog-a")
    assert replica_a["processed_ok"] == 3
    assert replica_a["stale"] is False


async def test_stale_uses_observed_at_and_monitor_setting(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, heartbeat_stale_seconds=30)
    ingestion = IngestionRepository(session)
    await ingestion.upsert_heartbeat(
        worker_type="discovery",
        instance_id="d1",
        status="idle",
        current_subject=None,
        processed_ok=0,
        processed_failed=0,
        lag_hint=None,
        observed_at=NOW - timedelta(seconds=31),
    )
    await ingestion.upsert_heartbeat(
        worker_type="reviews",
        instance_id="r1",
        status="idle",
        current_subject=None,
        processed_ok=0,
        processed_failed=0,
        lag_hint=None,
        observed_at=NOW - timedelta(seconds=10),
    )
    await session.commit()
    app = _app(
        settings,
        engine=engine,
        session_factory=session_factory,
        postgres_ready=_always_ready,
        clock=lambda: NOW,
    )
    async for client in _client(app):
        body = (await client.get("/api/v1/monitor")).json()
        by_type = {row["worker_type"]: row for row in body["workers"]}
        assert by_type["discovery"]["stale"] is True
        assert by_type["reviews"]["stale"] is False


async def test_circuit_failed_degraded_parse_error_and_no_secrets(
    monitor_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    ingestion = IngestionRepository(session)
    run = await ingestion.create_run(
        process_date=PROCESS_DATE,
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.cron,
    )
    assert isinstance(run.id, UUID)
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="ok",
        process_date=PROCESS_DATE,
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.completed,
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="failed",
        process_date=PROCESS_DATE,
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.failed,
        error_type="NotFoundError",
        error_message="api_key=sk-secret prompt=do not leak transcript=full text",
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="degraded",
        process_date=PROCESS_DATE,
        stage=IngestionStage.letsplay,
        status=IngestionItemStatus.degraded,
        error_type="QuotaError",
        error_message="quota",
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="parse",
        process_date=PROCESS_DATE,
        stage=IngestionStage.discovered,
        status=IngestionItemStatus.failed,
        error_type="ParseError",
        error_message="<html>raw</html>",
    )
    await ingestion.upsert_adapter_health(
        adapter_name="metacritic",
        circuit_state="open",
        parse_error_streak=3,
        opened_at=NOW,
        last_parse_error_at=NOW,
    )
    await ingestion.advance_cursor(PROCESS_DATE, new_releases_done=True, last_browse_page=2)
    await session.commit()

    response = await monitor_client.get("/api/v1/monitor")
    assert response.status_code == 200
    raw = response.text
    body = response.json()
    assert "sk-secret" not in raw
    assert "prompt=" not in raw
    assert "transcript=" not in raw
    assert "<html>" not in raw
    assert body["scrape"]["circuit_state"] == "open"
    assert body["scrape"]["parse_error_count"] == 1
    assert body["scrape"]["last_parse_error_at"] is not None
    counts = {(row["stage"], row["status"]): row["count"] for row in body["counts"]}
    assert counts[("cataloged", "failed")] == 1
    assert counts[("letsplay", "degraded")] == 1
    assert counts[("cataloged", "completed")] == 1
    assert body["cursor"]["new_releases_done"] is True
    assert body["cursor"]["last_browse_page"] == 2
    assert len(body["runs"]) == 1
    items = body["items"]
    assert len(items) == 4
    failed = next(row for row in items if row["metacritic_slug"] == "failed")
    assert failed["status"] == "failed"
    assert failed["error_type"] == "NotFoundError"
    assert failed["error_message"] is not None
    assert "sk-secret" not in failed["error_message"]
    assert "prompt=" not in failed["error_message"]
    parse_item = next(row for row in items if row["metacritic_slug"] == "parse")
    assert parse_item["error_message"] == "html omitted"


async def test_post_runs_202_writes_outbox_without_waiting(
    monitor_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    before = datetime.now(UTC)
    response = await monitor_client.post("/api/v1/runs")
    elapsed = (datetime.now(UTC) - before).total_seconds()
    assert response.status_code == 202
    assert elapsed < 2
    body = response.json()
    assert body["status"] == "run_accepted"
    assert body["process_date"] == PROCESS_DATE.isoformat()
    rows = await OutboxRepository(session).claim("api", limit=10)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["source"] == "urn:games-intel:api"
    assert payload["type"] == "ingestion.schedule.tick"
    assert payload["data"]["trigger"] == "manual"
    assert payload["data"]["process_date"] == PROCESS_DATE.isoformat()
    assert payload["subject"] == PROCESS_DATE.isoformat()
    assert "slug" not in payload["data"]
    assert "metacritic_slug" not in payload["data"]


async def test_post_runs_process_date_from_timezone(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    base = _settings(tmp_path)
    settings = base.model_copy(
        update={"app": base.app.model_copy(update={"process_timezone": "America/New_York"})}
    )
    when = datetime(2026, 9, 8, 2, 30, tzinfo=UTC)
    app = _app(
        settings,
        engine=engine,
        session_factory=session_factory,
        postgres_ready=_always_ready,
        clock=lambda: when,
    )
    async for client in _client(app):
        response = await client.post("/api/v1/runs")
        assert response.status_code == 202
        assert response.json()["process_date"] == "2026-09-07"
    rows = await OutboxRepository(session).claim("api", limit=1)
    assert rows[0].payload["data"]["process_date"] == "2026-09-07"


async def test_post_outbox_then_scheduler_creates_run(
    monitor_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    posted = await monitor_client.post("/api/v1/runs")
    assert posted.status_code == 202
    rows = await OutboxRepository(session).claim("api", limit=1)
    event = parse_cloud_event(encode_payload(rows[0].payload), Settings())
    await SchedulerHandler(Settings()).handle(event, session)
    await session.commit()
    listed = await monitor_client.get("/api/v1/monitor")
    runs = listed.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["trigger"] == "manual"
    assert runs[0]["status"] == "requested"


async def test_sse_emits_monitor_frame(monitor_client: httpx.AsyncClient) -> None:
    from games_intel.api.routers_monitor import iter_monitor_sse_frames
    from games_intel.api.schemas import MonitorSnapshot

    snapshot = (await monitor_client.get("/api/v1/monitor")).json()
    calls = {"n": 0}

    async def load() -> MonitorSnapshot:
        return MonitorSnapshot.model_validate(snapshot)

    async def disconnected() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    async def no_sleep(_delay: float) -> None:
        return None

    frames = [
        chunk
        async for chunk in iter_monitor_sse_frames(
            load,
            poll_seconds=0.2,
            disconnected=disconnected,
            sleep=no_sleep,
        )
    ]
    assert len(frames) == 1
    text = frames[0].decode()
    assert text.startswith("data: ")
    assert text.endswith("\n\n")
    frame = json.loads(text.removeprefix("data: ").strip())
    assert "workers" in frame
    assert "scrape" in frame
    assert "items" in frame
    assert frame["process_date"] == snapshot["process_date"]
    schema = create_app(Settings(), postgres_ready=_never_ready, kafka_ready=_never_ready).openapi()
    stream = schema["paths"]["/api/v1/monitor/stream"]["get"]["responses"]["200"]
    assert "text/event-stream" in stream["content"]


async def test_monitor_503_without_database() -> None:
    app = create_app(Settings(), postgres_ready=_never_ready, kafka_ready=_never_ready)
    async for client in _client(app):
        response = await client.get("/api/v1/monitor")
        assert response.status_code == 503
        assert response.headers["content-type"].startswith(PROBLEM_JSON)
        posted = await client.post("/api/v1/runs")
        assert posted.status_code == 503
