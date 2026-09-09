from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.payloads import SimilarityRecomputeRequested
from games_intel.db.records import OutboxInsert
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import InsertOutcome
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings
from games_intel.workers.scheduler.clock import process_date_for

_WORKER_TYPE = "scheduler"


def full_recompute_idempotency_key(settings: Settings, when: datetime) -> str:
    """`{recompute_type}:{process_date}:{yyyy-mm-ddTHH}:all:recompute` — one per hour."""
    day = process_date_for(settings, when)
    hour_stamp = when.strftime("%Y-%m-%dT%H")
    return (
        f"{settings.event_name('similarity_recompute')}:"
        f"{day.isoformat()}:"
        f"{hour_stamp}:all:recompute"
    )


async def enqueue_full_recompute(
    session: AsyncSession,
    settings: Settings,
    *,
    when: datetime,
) -> InsertOutcome:
    """Outbox `kafka.events.similarity_recompute` scope=all, reason=schedule. No worker names."""
    process_date = process_date_for(settings, when)
    hour_stamp = when.strftime("%Y-%m-%dT%H")
    payload = SimilarityRecomputeRequested(
        run_id=None,
        process_date=process_date,
        scope="all",
        center_slug=None,
        candidate_slugs=[],
        reason="schedule",
    )
    event = build_cloud_event(
        settings,
        "similarity_recompute",
        source=worker_source(settings, _WORKER_TYPE),
        subject=f"{hour_stamp}:all",
        data=payload,
        stage="recompute",
        run_id=None,
        occurred_at=when,
        idempotency_key=full_recompute_idempotency_key(settings, when),
    )
    result = await OutboxRepository(session).insert(
        OutboxInsert(
            producer=_WORKER_TYPE,
            idempotency_key=event.idempotencykey,
            topic=settings.event_name("similarity_recompute"),
            partition_key=process_date.isoformat(),
            payload=cloud_event_to_dict(event),
        )
    )
    return result.outcome
