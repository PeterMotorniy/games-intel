from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.db.mapping import outbox_record, utcnow
from games_intel.db.models import Outbox
from games_intel.db.records import InsertResult, OutboxInsert, OutboxRecord
from games_intel.db.types import InsertOutcome


class OutboxRepository:
    """Transactional outbox insert and SKIP LOCKED claim for relay replicas."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, row: OutboxInsert) -> InsertResult:
        stmt = (
            insert(Outbox)
            .values(
                producer=row.producer,
                idempotency_key=row.idempotency_key,
                topic=row.topic,
                partition_key=row.partition_key,
                payload=row.payload,
            )
            .on_conflict_do_nothing(index_elements=[Outbox.idempotency_key])
            .returning(Outbox.id)
        )
        inserted_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if inserted_id is None:
            return InsertResult(outcome=InsertOutcome.duplicate, id=None)
        return InsertResult(outcome=InsertOutcome.inserted, id=int(inserted_id))

    async def insert_schedule_tick(
        self,
        *,
        producer: str,
        idempotency_key: str,
        topic: str,
        partition_key: str,
        payload: dict[str, object],
    ) -> InsertResult:
        """Query API write: enqueue a schedule tick CloudEvent. No domain game writes."""
        return await self.insert(
            OutboxInsert(
                producer=producer,
                idempotency_key=idempotency_key,
                topic=topic,
                partition_key=partition_key,
                payload=dict(payload),
            )
        )

    async def claim(self, producer: str, *, limit: int = 10) -> tuple[OutboxRecord, ...]:
        stmt = (
            select(Outbox)
            .where(Outbox.published_at.is_(None), Outbox.producer == producer)
            .order_by(Outbox.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        rows = (await self._session.scalars(stmt)).all()
        return tuple(outbox_record(row) for row in rows)

    async def mark_published(
        self, outbox_ids: Sequence[int], *, published_at: datetime | None = None
    ) -> None:
        if not outbox_ids:
            return
        when = published_at if published_at is not None else utcnow()
        await self._session.execute(
            update(Outbox).where(Outbox.id.in_(list(outbox_ids))).values(published_at=when)
        )
