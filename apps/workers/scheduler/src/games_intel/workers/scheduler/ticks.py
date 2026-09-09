from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.payloads import ScheduleTick, Trigger
from games_intel.db.records import OutboxInsert
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import InsertOutcome
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings
from games_intel.workers.scheduler.clock import process_date_for

_WORKER_TYPE = "scheduler"

Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def tick_dedup_key(settings: Settings, when: datetime) -> str:
    process_date = process_date_for(settings, when)
    window = max(settings.scheduler.tick_dedup_window_seconds, 1)
    bucket = int(when.timestamp() // window)
    event_type = settings.event_name(settings.scheduler.subscribe_event)
    return f"{event_type}:{process_date.isoformat()}:{bucket}:tick"


async def enqueue_schedule_tick(
    session: AsyncSession,
    settings: Settings,
    *,
    trigger: Trigger,
    when: datetime | None = None,
    clock: Clock | None = None,
) -> InsertOutcome:
    instant = when if when is not None else (clock or _utcnow)()
    if instant.tzinfo is None or instant.utcoffset() is None:
        instant = instant.replace(tzinfo=UTC)
    process_date = process_date_for(settings, instant)
    payload = ScheduleTick(
        trigger=trigger,
        requested_at=instant,
        process_date=process_date,
    )
    event = build_cloud_event(
        settings,
        settings.scheduler.subscribe_event,
        source=worker_source(settings, _WORKER_TYPE),
        subject=process_date.isoformat(),
        data=payload,
        stage="tick",
        occurred_at=instant,
        idempotency_key=tick_dedup_key(settings, instant),
    )
    result = await OutboxRepository(session).insert(
        OutboxInsert(
            producer=_WORKER_TYPE,
            idempotency_key=event.idempotencykey,
            topic=settings.event_name(settings.scheduler.subscribe_event),
            partition_key=process_date.isoformat(),
            payload=cloud_event_to_dict(event),
        )
    )
    return result.outcome
