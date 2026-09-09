from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.db.records import OutboxInsert
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.kafka.relay import OutboxRelay
from games_intel.kafka.testing import FakeBroker, FakeProducer


async def test_outbox_unique_key_publishes_once(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = OutboxRepository(session)
    row = OutboxInsert(
        producer="catalog",
        idempotency_key="game.cataloged:r:elden-ring:cataloged",
        topic="game.cataloged",
        partition_key="elden-ring",
        payload={"id": "ce-1", "type": "game.cataloged"},
    )
    first = await repo.insert(row)
    second = await repo.insert(row)
    await session.commit()
    assert first.outcome.value == "inserted"
    assert second.outcome.value == "duplicate"

    broker = FakeBroker()
    relay = OutboxRelay(session_factory, FakeProducer(broker), worker_type="catalog")
    published = await relay.publish_once()
    assert published == 1
    assert len(broker.topics["game.cataloged"]) == 1
    assert broker.topics["game.cataloged"][0].key == "elden-ring"

    again = await relay.publish_once()
    assert again == 0


async def test_produce_fail_leaves_unpublished(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = OutboxRepository(session)
    await repo.insert(
        OutboxInsert(
            producer="catalog",
            idempotency_key="game.cataloged:r:nightreign:cataloged",
            topic="game.cataloged",
            partition_key="nightreign",
            payload={"id": "ce-2", "type": "game.cataloged"},
        )
    )
    await session.commit()

    broker = FakeBroker()
    broker.fail_produce = True
    relay = OutboxRelay(session_factory, FakeProducer(broker), worker_type="catalog")
    assert await relay.publish_once() == 0
    claimed = await OutboxRepository(session).claim("catalog")
    assert len(claimed) == 1
    assert claimed[0].published_at is None
    await session.rollback()

    broker.fail_produce = False
    assert await relay.publish_once() == 1
    async with session_factory() as other:
        rows = await OutboxRepository(other).claim("catalog")
        assert rows == ()


async def test_produce_does_not_hold_row_lock(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await OutboxRepository(session).insert(
        OutboxInsert(
            producer="catalog",
            idempotency_key="k-lock",
            topic="game.cataloged",
            partition_key="slug",
            payload={"id": "lock-1"},
        )
    )
    await session.commit()
    seen: list[int] = []

    class ProbeProducer(FakeProducer):
        async def send(
            self,
            *,
            topic: str,
            key: str,
            value: bytes,
            headers: tuple[tuple[str, bytes], ...] = (),
        ) -> None:
            async with session_factory() as other:
                async with other.begin():
                    rows = await OutboxRepository(other).claim("catalog")
                    seen.extend(row.id for row in rows)
            await super().send(topic=topic, key=key, value=value, headers=headers)

    broker = FakeBroker()
    relay = OutboxRelay(session_factory, ProbeProducer(broker), worker_type="catalog")
    assert await relay.publish_once() == 1
    assert seen


async def test_relay_does_not_use_instance_as_producer(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = OutboxRepository(session)
    await repo.insert(
        OutboxInsert(
            producer="catalog",
            idempotency_key="k-1",
            topic="game.cataloged",
            partition_key="slug",
            payload={"id": "x"},
        )
    )
    await session.commit()
    broker = FakeBroker()
    instance_relay = OutboxRelay(
        session_factory, FakeProducer(broker), worker_type="catalog-instance-a"
    )
    assert await instance_relay.publish_once() == 0
    type_relay = OutboxRelay(session_factory, FakeProducer(broker), worker_type="catalog")
    assert await type_relay.publish_once() == 1
