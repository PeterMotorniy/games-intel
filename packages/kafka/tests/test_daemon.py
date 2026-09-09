from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.contracts import GameCataloged, GamesPageListed, ListedGame, build_cloud_event
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage, RunTrigger
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.exceptions import SchemaError, TransientError
from games_intel.kafka.logging import emit_json
from games_intel.kafka.serialization import encode_cloud_event
from games_intel.kafka.source import worker_source
from games_intel.kafka.testing import FakeBroker, FakeConsumer, FakeProducer
from games_intel.kafka.types import IncomingRecord
from games_intel.settings import Settings

RUN_ID = UUID("0191c0aa-7e3b-7000-8000-000000000001")
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
PROCESS_DATE = date(2026, 9, 7)


class StubHandler:
    def __init__(self, *, fail: Exception | None = None, fail_times: int = 0) -> None:
        self.calls = 0
        self.fail = fail
        self.fail_times = fail_times

    async def handle(self, event: Any, session: AsyncSession) -> None:
        self.calls += 1
        if self.fail is not None and self.calls <= self.fail_times:
            raise self.fail
        await GameCatalogRepository(session).ensure_game_stub(
            metacritic_slug=event.subject,
            title=event.data.title,
        )


def _settings() -> Settings:
    base = Settings()
    return base.model_copy(
        update={
            "retry": base.retry.model_copy(
                update={"max_attempts": 3, "backoff_base_seconds": 0, "jitter_ratio": 0}
            )
        }
    )


def _cataloged(*, event_id: str | None = None) -> Any:
    settings = _settings()
    data = GameCataloged.model_validate(
        {
            "run_id": RUN_ID,
            "process_date": PROCESS_DATE,
            "metacritic_slug": "elden-ring",
            "title": "Elden Ring",
        }
    )
    return build_cloud_event(
        settings,
        "game_cataloged",
        source=worker_source(settings, "catalog"),
        subject="elden-ring",
        data=data,
        stage="cataloged",
        run_id=RUN_ID,
        event_id=event_id,
        occurred_at=NOW,
    )


def _record(event: Any) -> IncomingRecord:
    settings = _settings()
    return IncomingRecord(
        topic=settings.event_name("game_cataloged"),
        partition=0,
        offset=0,
        key=event.subject,
        value=encode_cloud_event(event),
    )


def _page_listed(*, event_id: str) -> Any:
    settings = _settings()
    data = GamesPageListed(
        run_id=RUN_ID,
        process_date=PROCESS_DATE,
        source="new_releases",
        page=None,
        games=[
            ListedGame(
                metacritic_slug="elden-ring",
                title="Elden Ring",
                listing_url=HttpUrl("https://www.metacritic.com/game/elden-ring/"),
                position=0,
            ),
            ListedGame(
                metacritic_slug="sekiro",
                title="Sekiro",
                listing_url=HttpUrl("https://www.metacritic.com/game/sekiro/"),
                position=1,
            ),
        ],
    )
    return build_cloud_event(
        settings,
        "page_listed",
        source=worker_source(settings, "discovery"),
        subject=str(RUN_ID),
        data=data,
        stage="discovered",
        run_id=RUN_ID,
        event_id=event_id,
        occurred_at=NOW,
    )


def _loop(
    session_factory: async_sessionmaker[AsyncSession],
    handler: StubHandler,
    *,
    instance_id: str = "catalog-1",
    worker_type: str = "catalog",
    stage_name: str = "cataloged",
    subscribe_event_key: str = "game_cataloged",
    consumer: FakeConsumer | None = None,
    producer: FakeProducer | None = None,
) -> tuple[DaemonLoop, FakeBroker, FakeConsumer]:
    settings = _settings()
    broker = producer.broker if producer is not None else FakeBroker()
    fake_producer = producer or FakeProducer(broker)
    fake_consumer = consumer or FakeConsumer(broker, (settings.event_name(subscribe_event_key),))
    loop = DaemonLoop(
        settings,
        DaemonConfig(
            worker_type=worker_type,
            instance_id=instance_id,
            stage_name=stage_name,
            subscribe_event_key=subscribe_event_key,
        ),
        consumer=fake_consumer,
        producer=fake_producer,
        session_factory=session_factory,
        handler=handler,
        sleep=_no_sleep,
    )
    return loop, broker, fake_consumer


async def _no_sleep(_delay: float) -> None:
    return None


async def _seed_run(session: AsyncSession) -> None:
    await IngestionRepository(session).create_run(
        process_date=PROCESS_DATE,
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.manual,
        run_id=RUN_ID,
    )
    await session.commit()


async def test_parallel_handlers_persist_once(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    event = _cataloged(event_id="evt-parallel")
    record = _record(event)
    handler_a = StubHandler()
    handler_b = StubHandler()
    loop_a, _, consumer_a = _loop(session_factory, handler_a, instance_id="a")
    loop_b, _, consumer_b = _loop(session_factory, handler_b, instance_id="b")
    await asyncio.gather(loop_a.process_record(record), loop_b.process_record(record))
    assert sorted((handler_a.calls, handler_b.calls)) == [0, 1]
    game = await GameCatalogRepository(session).get_by_slug("elden-ring")
    assert game is not None
    assert consumer_a.committed[(record.topic, 0)] == 1
    assert consumer_b.committed[(record.topic, 0)] == 1


async def test_same_cataloged_event_runs_catalog_reviews_and_letsplay(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    event = _cataloged(event_id="evt-shared-cataloged")
    record = _record(event)
    catalog = StubHandler()
    reviews = StubHandler()
    letsplay = StubHandler()
    catalog_loop, _, catalog_consumer = _loop(
        session_factory,
        catalog,
        instance_id="catalog-1",
        worker_type="catalog",
        stage_name="cataloged",
    )
    reviews_loop, _, reviews_consumer = _loop(
        session_factory,
        reviews,
        instance_id="reviews-1",
        worker_type="reviews",
        stage_name="reviews",
        consumer=FakeConsumer(FakeBroker(), (_settings().event_name("game_cataloged"),)),
    )
    letsplay_loop, _, letsplay_consumer = _loop(
        session_factory,
        letsplay,
        instance_id="letsplay-1",
        worker_type="letsplay",
        stage_name="letsplay",
        consumer=FakeConsumer(FakeBroker(), (_settings().event_name("game_cataloged"),)),
    )
    await catalog_loop.process_record(record)
    await reviews_loop.process_record(record)
    await letsplay_loop.process_record(record)
    assert catalog.calls == 1
    assert reviews.calls == 1
    assert letsplay.calls == 1
    assert catalog_consumer.committed[(record.topic, 0)] == 1
    assert reviews_consumer.committed[(record.topic, 0)] == 1
    assert letsplay_consumer.committed[(record.topic, 0)] == 1


async def test_new_event_id_same_business_key_is_noop(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    first = _cataloged(event_id="id-a")
    second = _cataloged(event_id="id-b")
    assert first.id != second.id
    assert first.idempotencykey == second.idempotencykey
    handler = StubHandler()
    loop, _, consumer = _loop(session_factory, handler)
    await loop.process_record(_record(first))
    await loop.process_record(
        IncomingRecord(
            topic=_settings().event_name("game_cataloged"),
            partition=0,
            offset=1,
            key=second.subject,
            value=encode_cloud_event(second),
        )
    )
    assert handler.calls == 1
    assert consumer.committed[(_settings().event_name("game_cataloged"), 0)] == 2


async def test_schema_poison_dlq_then_valid(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    settings = _settings()
    topic = settings.event_name("game_cataloged")
    handler = StubHandler()
    loop, broker, consumer = _loop(session_factory, handler)
    poison = IncomingRecord(topic=topic, partition=0, offset=0, key="x", value=b"not-json")
    valid = _record(_cataloged(event_id="valid-1"))
    valid = IncomingRecord(
        topic=valid.topic,
        partition=0,
        offset=1,
        key=valid.key,
        value=valid.value,
    )
    await loop.process_record(poison)
    await loop.process_record(valid)
    dlq_topic = settings.event_name("dlq")
    assert len(broker.topics[dlq_topic]) == 1
    dlq = json.loads(broker.topics[dlq_topic][0].value.decode("utf-8"))
    assert dlq["data"]["reason"] == "schema"
    game = await GameCatalogRepository(session).get_by_slug("elden-ring")
    assert game is not None
    assert handler.calls == 1
    assert consumer.committed[(topic, 0)] == 2


async def test_transient_max_attempts_fails_item(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    handler = StubHandler(fail=TransientError("sidecar timeout"), fail_times=10)
    loop, broker, consumer = _loop(session_factory, handler)
    record = _record(_cataloged(event_id="evt-transient"))
    await loop.process_record(record)
    assert handler.calls == 3
    item = await IngestionRepository(session).get_item(
        RUN_ID, "elden-ring", IngestionStage.cataloged
    )
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.attempt_count == 3
    assert consumer.committed[(record.topic, 0)] == 1
    dlq = json.loads(broker.topics[_settings().event_name("dlq")][0].value.decode("utf-8"))
    assert dlq["data"]["reason"] == "timeout"
    assert await GameCatalogRepository(session).get_by_slug("elden-ring") is None


async def test_page_listed_transient_fails_game_slugs_not_run_id(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    handler = StubHandler(fail=TransientError("sidecar timeout"), fail_times=10)
    event = _page_listed(event_id="evt-page-transient")
    settings = _settings()
    loop, broker, consumer = _loop(session_factory, handler, subscribe_event_key="page_listed")
    record = IncomingRecord(
        topic=settings.event_name("page_listed"),
        partition=0,
        offset=0,
        key=event.subject,
        value=encode_cloud_event(event),
    )
    await loop.process_record(record)
    assert handler.calls == 3
    ingestion = IngestionRepository(session)
    first = await ingestion.get_item(RUN_ID, "elden-ring", IngestionStage.cataloged)
    second = await ingestion.get_item(RUN_ID, "sekiro", IngestionStage.cataloged)
    bogus = await ingestion.get_item(RUN_ID, str(RUN_ID), IngestionStage.cataloged)
    assert first is not None and first.status is IngestionItemStatus.failed
    assert second is not None and second.status is IngestionItemStatus.failed
    assert first.attempt_count == 3
    assert bogus is None
    assert consumer.committed[(record.topic, 0)] == 1
    dlq = json.loads(broker.topics[settings.event_name("dlq")][0].value.decode("utf-8"))
    assert dlq["data"]["reason"] == "timeout"


async def test_unexpected_handler_error_dlq_and_commits(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    handler = StubHandler(fail=RuntimeError("boom"), fail_times=10)
    loop, broker, consumer = _loop(session_factory, handler)
    record = _record(_cataloged(event_id="evt-boom"))
    await loop.process_record(record)
    assert handler.calls == 1
    item = await IngestionRepository(session).get_item(
        RUN_ID, "elden-ring", IngestionStage.cataloged
    )
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.error_type == "RuntimeError"
    assert consumer.committed[(record.topic, 0)] == 1
    dlq = json.loads(broker.topics[_settings().event_name("dlq")][0].value.decode("utf-8"))
    assert dlq["data"]["reason"] == "handler"
    assert await GameCatalogRepository(session).get_by_slug("elden-ring") is None


async def test_two_catalog_replicas_write_separate_heartbeats(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    event = _cataloged(event_id="evt-hb")
    record = _record(event)
    loop_a, _, _ = _loop(session_factory, StubHandler(), instance_id="catalog-a")
    loop_b, _, _ = _loop(session_factory, StubHandler(), instance_id="catalog-b")
    await loop_a.process_record(record)
    await loop_b.process_record(record)
    beats = await IngestionRepository(session).list_heartbeats()
    catalog = [row for row in beats if row.worker_type == "catalog"]
    instance_ids = {row.instance_id for row in catalog}
    assert instance_ids == {"catalog-a", "catalog-b"}
    assert all(row.processed_ok >= 0 for row in catalog)


async def test_schema_error_does_not_change_domain(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    handler = StubHandler()
    loop, _, _ = _loop(session_factory, handler)
    await loop.process_record(
        IncomingRecord(
            topic=_settings().event_name("game_cataloged"),
            partition=0,
            offset=0,
            key="x",
            value=b'{"specversion":"1.0"}',
        )
    )
    assert handler.calls == 0
    assert await GameCatalogRepository(session).get_by_slug("elden-ring") is None


def test_json_logs_required_fields_without_secrets(caplog: Any) -> None:
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("games_intel.kafka.test")
    emit_json(
        logger,
        run_id=str(RUN_ID),
        slug="elden-ring",
        worker="catalog",
        stage="cataloged",
        event_id="evt-1",
        error_type=SchemaError.__name__,
        attempt=1,
        token="secret-token",
        html="<html>nope</html>",
    )
    assert caplog.records
    payload = json.loads(caplog.records[-1].message)
    assert payload["run_id"] == str(RUN_ID)
    assert payload["slug"] == "elden-ring"
    assert payload["worker"] == "catalog"
    assert payload["stage"] == "cataloged"
    assert payload["event_id"] == "evt-1"
    assert payload["error_type"] == "SchemaError"
    assert payload["attempt"] == 1
    assert "token" not in payload
    assert "html" not in payload
    assert "<html" not in caplog.records[-1].message
