from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.contracts import GameCataloged, build_cloud_event
from games_intel.db.records import OutboxInsert
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage, RunTrigger
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.exceptions import TransientError
from games_intel.kafka.relay import OutboxRelay
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


class _CrashAfterBackoff(Exception):
    """Simulates process kill during Transient backoff."""


def _settings() -> Settings:
    base = Settings()
    return base.model_copy(
        update={
            "retry": base.retry.model_copy(
                update={"max_attempts": 5, "backoff_base_seconds": 0, "jitter_ratio": 0}
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


def _loop(
    session_factory: async_sessionmaker[AsyncSession],
    handler: StubHandler,
    *,
    consumer: FakeConsumer | None = None,
    producer: FakeProducer | None = None,
    sleep: Any = _no_sleep,
) -> tuple[DaemonLoop, FakeBroker, FakeConsumer]:
    settings = _settings()
    broker = producer.broker if producer is not None else FakeBroker()
    fake_producer = producer or FakeProducer(broker)
    fake_consumer = consumer or FakeConsumer(broker, (settings.event_name("game_cataloged"),))
    loop = DaemonLoop(
        settings,
        DaemonConfig(
            worker_type="catalog",
            instance_id="catalog-1",
            stage_name="cataloged",
            subscribe_event_key="game_cataloged",
        ),
        consumer=fake_consumer,
        producer=fake_producer,
        session_factory=session_factory,
        handler=handler,
        sleep=sleep,
    )
    return loop, broker, fake_consumer


async def test_kill_after_persist_before_offset_no_duplicate_domain(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    event = _cataloged(event_id="evt-kill-offset")
    record = _record(event)
    settings = _settings()
    broker = FakeBroker()
    consumer = FakeConsumer(
        broker,
        (settings.event_name("game_cataloged"),),
        fail_commit_times=1,
    )
    handler = StubHandler()
    loop, _, _ = _loop(session_factory, handler, consumer=consumer, producer=FakeProducer(broker))
    try:
        await loop.process_record(record)
    except RuntimeError as exc:
        assert "before offset" in str(exc)
    else:
        raise AssertionError("expected commit to fail once")
    assert handler.calls == 1
    assert consumer.committed == {}
    game = await GameCatalogRepository(session).get_by_slug("elden-ring")
    assert game is not None

    await loop.process_record(
        IncomingRecord(
            topic=record.topic,
            partition=0,
            offset=0,
            key=record.key,
            value=record.value,
        )
    )
    assert handler.calls == 1
    again = await GameCatalogRepository(session).get_by_slug("elden-ring")
    assert again is not None
    assert again.id == game.id
    assert consumer.committed[(record.topic, 0)] == 1


async def test_unpublished_outbox_published_after_relay_restart(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = OutboxRepository(session)
    await repo.insert(
        OutboxInsert(
            producer="catalog",
            idempotency_key="game.cataloged:r:elden-ring:cataloged",
            topic="game.cataloged",
            partition_key="elden-ring",
            payload={"id": "ce-restart", "type": "game.cataloged"},
        )
    )
    await session.commit()

    broker = FakeBroker()
    broker.fail_produce = True
    first = OutboxRelay(session_factory, FakeProducer(broker), worker_type="catalog")
    assert await first.publish_once() == 0

    restarted = OutboxRelay(session_factory, FakeProducer(broker), worker_type="catalog")
    broker.fail_produce = False
    assert await restarted.publish_once() == 1
    async with session_factory() as other:
        assert await OutboxRepository(other).claim("catalog") == ()
    assert len(broker.topics["game.cataloged"]) == 1


async def test_attempt_count_survives_process_restart(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_run(session)
    record = _record(_cataloged(event_id="evt-attempt-restart"))
    sleeps = {"n": 0}

    async def sleep_then_crash(_delay: float) -> None:
        sleeps["n"] += 1
        if sleeps["n"] >= 2:
            raise _CrashAfterBackoff()

    first_handler = StubHandler(fail=TransientError("sidecar timeout"), fail_times=10)
    loop_one, _, consumer = _loop(session_factory, first_handler, sleep=sleep_then_crash)
    try:
        await loop_one.process_record(record)
    except _CrashAfterBackoff:
        pass
    else:
        raise AssertionError("expected crash during backoff")
    assert first_handler.calls == 2
    item = await IngestionRepository(session).get_item(
        RUN_ID, "elden-ring", IngestionStage.cataloged
    )
    assert item is not None
    assert item.attempt_count == 2
    assert item.status is IngestionItemStatus.running
    assert consumer.committed == {}

    second_handler = StubHandler(fail=TransientError("sidecar timeout"), fail_times=10)
    loop_two, _, consumer_two = _loop(session_factory, second_handler)
    await loop_two.process_record(record)
    assert second_handler.calls == 3
    session.expire_all()
    item = await IngestionRepository(session).get_item(
        RUN_ID, "elden-ring", IngestionStage.cataloged
    )
    assert item is not None
    assert item.attempt_count == 5
    assert item.status is IngestionItemStatus.failed
    assert consumer_two.committed[(record.topic, 0)] == 1
