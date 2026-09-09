from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.payloads import RunRequested, RunSource, ScheduleTick
from games_intel.db.records import OutboxInsert
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import InsertOutcome, RunTrigger
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings
from games_intel.workers.scheduler.source import decide_source_and_page

_WORKER_TYPE = "scheduler"
_ALLOWED_SOURCES: frozenset[str] = frozenset({"new_releases", "browse"})
_CLAIM_ATTEMPTS = 16


class SchedulerHandler:
    """Consume schedule ticks; persist a unique run; outbox run.requested. No site adapters."""

    def __init__(self, settings: Settings, *, use_lock: bool = True) -> None:
        self.settings = settings
        self.use_lock = use_lock
        self.lock_attempts = 0
        self.lock_acquired = 0
        self.runs_created = 0

    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None:
        tick = event.data
        if not isinstance(tick, ScheduleTick):
            msg = "scheduler expected ScheduleTick payload"
            raise TypeError(msg)
        ingestion = IngestionRepository(session)
        if self.use_lock:
            self.lock_attempts += 1
            acquired = await ingestion.try_advisory_lock(self.settings.scheduler.advisory_lock_key)
            if not acquired:
                return
            self.lock_acquired += 1
        for _ in range(_CLAIM_ATTEMPTS):
            source, page = decide_source_and_page(
                await ingestion.get_cursor(tick.process_date),
                self.settings,
                await ingestion.list_runs_for_date(tick.process_date),
            )
            created = await ingestion.create_run(
                process_date=tick.process_date,
                source=source,
                page=page,
                limit=self.settings.scheduler.default_limit,
                trigger=RunTrigger(tick.trigger),
            )
            if created.outcome is InsertOutcome.duplicate or created.id is None:
                continue
            run_id = created.id
            if not isinstance(run_id, UUID):
                msg = "create_run must return a UUID run id"
                raise TypeError(msg)
            self.runs_created += 1
            await _enqueue_run_requested(
                session,
                self.settings,
                tick=tick,
                run_id=run_id,
                source=source,
                page=page,
            )
            return


async def _enqueue_run_requested(
    session: AsyncSession,
    settings: Settings,
    *,
    tick: ScheduleTick,
    run_id: UUID,
    source: str,
    page: int | None,
) -> None:
    if source not in _ALLOWED_SOURCES:
        msg = f"unsupported scheduler source: {source}"
        raise ValueError(msg)
    payload = RunRequested(
        run_id=run_id,
        process_date=tick.process_date,
        source=cast(RunSource, source),
        page=page,
        limit=settings.scheduler.default_limit,
        trigger=tick.trigger,
    )
    event = build_cloud_event(
        settings,
        settings.scheduler.publish_event,
        source=worker_source(settings, _WORKER_TYPE),
        subject=str(run_id),
        data=payload,
        stage=settings.scheduler.stage_name,
        run_id=run_id,
    )
    await OutboxRepository(session).insert(
        OutboxInsert(
            producer=_WORKER_TYPE,
            idempotency_key=event.idempotencykey,
            topic=settings.event_name(settings.scheduler.publish_event),
            partition_key=str(run_id),
            payload=cloud_event_to_dict(event),
        )
    )
