from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.db.mapping import (
    adapter_health_record,
    cursor_record,
    heartbeat_record,
    item_record,
    run_record,
    utcnow,
)
from games_intel.db.models import (
    AdapterHealth,
    DailyProcessedSlug,
    Game,
    IngestionCursor,
    IngestionItem,
    IngestionRun,
    ProcessedEvent,
    WorkerHeartbeat,
)
from games_intel.db.records import (
    AdapterHealthRecord,
    HeartbeatRecord,
    IngestionCursorRecord,
    IngestionItemRecord,
    IngestionRunRecord,
    InsertResult,
    MonitorAggregates,
    MonitorItemRecord,
    StageStatusCount,
)
from games_intel.db.types import (
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionStage,
    InsertOutcome,
    RunTrigger,
)


class IngestionRepository:
    """Scheduler/Discovery/workers: cursors, runs, items, daily slugs, idempotency, heartbeats."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_cursor(self, process_date: date) -> IngestionCursorRecord | None:
        row = await self._session.get(IngestionCursor, process_date)
        if row is None:
            return None
        return cursor_record(row)

    async def advance_cursor(
        self,
        process_date: date,
        *,
        new_releases_done: bool,
        last_browse_page: int | None,
    ) -> IngestionCursorRecord:
        """Move the day cursor only after a successful listing (including empty/all-seen)."""
        now = utcnow()
        stmt = (
            insert(IngestionCursor)
            .values(
                process_date=process_date,
                new_releases_done=new_releases_done,
                last_browse_page=last_browse_page,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[IngestionCursor.process_date],
                set_={
                    "new_releases_done": new_releases_done,
                    "last_browse_page": last_browse_page,
                    "updated_at": now,
                },
            )
            .returning(IngestionCursor)
        )
        row = (await self._session.execute(stmt)).scalar_one()
        return cursor_record(row)

    async def create_run(
        self,
        *,
        process_date: date,
        source: str,
        page: int | None,
        limit: int,
        trigger: RunTrigger,
        status: IngestionRunStatus = IngestionRunStatus.requested,
        run_id: UUID | None = None,
    ) -> InsertResult[UUID]:
        run = IngestionRun(
            id=run_id or uuid4(),
            process_date=process_date,
            source=source,
            page=page,
            limit=limit,
            trigger=trigger.value,
            status=status.value,
            discovered_count=0,
            started_at=utcnow(),
        )
        try:
            async with self._session.begin_nested():
                self._session.add(run)
                await self._session.flush()
        except IntegrityError:
            existing = await self._active_run(process_date, source, page)
            return InsertResult(
                outcome=InsertOutcome.duplicate,
                id=None if existing is None else existing.id,
            )
        return InsertResult(outcome=InsertOutcome.inserted, id=run.id)

    async def get_run(self, run_id: UUID) -> IngestionRunRecord | None:
        row = await self._session.get(IngestionRun, run_id)
        if row is None:
            return None
        return run_record(row)

    async def list_runs_for_date(self, process_date: date) -> tuple[IngestionRunRecord, ...]:
        stmt = (
            select(IngestionRun)
            .where(IngestionRun.process_date == process_date)
            .order_by(IngestionRun.id)
        )
        rows = (await self._session.scalars(stmt)).all()
        return tuple(run_record(row) for row in rows)

    async def update_run(
        self,
        run_id: UUID,
        *,
        status: IngestionRunStatus | None = None,
        discovered_count: int | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        values: dict[str, object] = {}
        if status is not None:
            values["status"] = status.value
        if discovered_count is not None:
            values["discovered_count"] = discovered_count
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if not values:
            return
        await self._session.execute(
            update(IngestionRun).where(IngestionRun.id == run_id).values(**values)
        )

    async def record_daily_processed_slug(
        self, process_date: date, metacritic_slug: str
    ) -> InsertOutcome:
        """Catalog: mark slug as taken for the calendar day after a card is cataloged or 404."""
        stmt = (
            insert(DailyProcessedSlug)
            .values(process_date=process_date, metacritic_slug=metacritic_slug)
            .on_conflict_do_nothing()
            .returning(DailyProcessedSlug.metacritic_slug)
        )
        inserted = (await self._session.execute(stmt)).scalar_one_or_none()
        return InsertOutcome.inserted if inserted is not None else InsertOutcome.duplicate

    async def is_slug_processed_today(self, process_date: date, metacritic_slug: str) -> bool:
        row = await self._session.get(DailyProcessedSlug, (process_date, metacritic_slug))
        return row is not None

    async def list_daily_processed_slugs(self, process_date: date) -> tuple[str, ...]:
        stmt = (
            select(DailyProcessedSlug.metacritic_slug)
            .where(DailyProcessedSlug.process_date == process_date)
            .order_by(DailyProcessedSlug.metacritic_slug)
        )
        rows = (await self._session.scalars(stmt)).all()
        return tuple(rows)

    async def try_advisory_lock(self, key: int) -> bool:
        """Transaction-scoped lock; released on COMMIT/ROLLBACK if not held elsewhere."""
        acquired = await self._session.scalar(
            text("SELECT pg_try_advisory_xact_lock(:key)"),
            {"key": int(key)},
        )
        return bool(acquired)

    async def upsert_item(
        self,
        *,
        run_id: UUID,
        metacritic_slug: str,
        process_date: date,
        stage: IngestionStage,
        status: IngestionItemStatus,
        game_id: UUID | None = None,
        event_id: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        attempt_count: int | None = None,
    ) -> InsertResult[UUID]:
        now = utcnow()
        values: dict[str, Any] = {
            "run_id": run_id,
            "metacritic_slug": metacritic_slug,
            "process_date": process_date,
            "stage": stage.value,
            "status": status.value,
            "game_id": game_id,
            "event_id": event_id,
            "error_type": error_type,
            "error_message": error_message,
            "updated_at": now,
        }
        if attempt_count is not None:
            values["attempt_count"] = attempt_count
        set_on_conflict: dict[str, Any] = {
            "status": status.value,
            "game_id": game_id,
            "event_id": event_id,
            "error_type": error_type,
            "error_message": error_message,
            "updated_at": now,
        }
        if attempt_count is not None:
            set_on_conflict["attempt_count"] = attempt_count
        stmt = (
            insert(IngestionItem)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_ingestion_items_run_slug_stage",
                set_=set_on_conflict,
            )
            .returning(IngestionItem.id)
        )
        item_id = (await self._session.execute(stmt)).scalar_one()
        return InsertResult(outcome=InsertOutcome.inserted, id=item_id)

    async def latest_items_for_slugs(
        self, slugs: Sequence[str]
    ) -> dict[tuple[str, IngestionStage], IngestionItemRecord]:
        if not slugs:
            return {}
        stmt = (
            select(IngestionItem)
            .where(IngestionItem.metacritic_slug.in_(list(slugs)))
            .distinct(IngestionItem.metacritic_slug, IngestionItem.stage)
            .order_by(
                IngestionItem.metacritic_slug,
                IngestionItem.stage,
                IngestionItem.updated_at.desc(),
                IngestionItem.id.desc(),
            )
        )
        rows = (await self._session.scalars(stmt)).all()
        return {(row.metacritic_slug, IngestionStage(row.stage)): item_record(row) for row in rows}

    async def latest_items_for_slug(
        self, metacritic_slug: str
    ) -> dict[tuple[str, IngestionStage], IngestionItemRecord]:
        return await self.latest_items_for_slugs((metacritic_slug,))

    async def get_item(
        self, run_id: UUID, metacritic_slug: str, stage: IngestionStage
    ) -> IngestionItemRecord | None:
        stmt = select(IngestionItem).where(
            IngestionItem.run_id == run_id,
            IngestionItem.metacritic_slug == metacritic_slug,
            IngestionItem.stage == stage.value,
        )
        row = await self._session.scalar(stmt)
        if row is None:
            return None
        return item_record(row)

    async def try_claim_item(
        self,
        *,
        run_id: UUID,
        metacritic_slug: str,
        process_date: date,
        stage: IngestionStage,
        instance_id: str,
        lease_seconds: int,
        event_id: str | None = None,
    ) -> bool:
        """Commit-scoped work lease. False if another replica holds a live lease."""
        now = utcnow()
        until = now + timedelta(seconds=max(int(lease_seconds), 1))
        values: dict[str, Any] = {
            "run_id": run_id,
            "metacritic_slug": metacritic_slug,
            "process_date": process_date,
            "stage": stage.value,
            "status": IngestionItemStatus.running.value,
            "event_id": event_id,
            "claimed_until": until,
            "claimed_by": instance_id,
            "updated_at": now,
        }
        stmt = (
            insert(IngestionItem)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_ingestion_items_run_slug_stage",
                set_={
                    "status": IngestionItemStatus.running.value,
                    "event_id": event_id,
                    "claimed_until": until,
                    "claimed_by": instance_id,
                    "updated_at": now,
                },
                where=(
                    (IngestionItem.claimed_until.is_(None))
                    | (IngestionItem.claimed_until <= now)
                    | (IngestionItem.claimed_by == instance_id)
                ),
            )
            .returning(IngestionItem.id)
        )
        claimed_id = (await self._session.execute(stmt)).scalar_one_or_none()
        return claimed_id is not None

    async def lock_item(
        self,
        run_id: UUID,
        metacritic_slug: str,
        stage: IngestionStage,
        *,
        lease_seconds: int,
    ) -> IngestionItemRecord | None:
        timeout_ms = max(int(lease_seconds), 0) * 1000
        await self._session.execute(text(f"SET LOCAL lock_timeout = '{timeout_ms}ms'"))
        stmt = (
            select(IngestionItem)
            .where(
                IngestionItem.run_id == run_id,
                IngestionItem.metacritic_slug == metacritic_slug,
                IngestionItem.stage == stage.value,
            )
            .with_for_update(skip_locked=True)
        )
        row = await self._session.scalar(stmt)
        if row is None:
            return None
        return item_record(row)

    async def increment_attempt(self, item_id: UUID) -> int:
        stmt = (
            update(IngestionItem)
            .where(IngestionItem.id == item_id)
            .values(
                attempt_count=IngestionItem.attempt_count + 1,
                updated_at=utcnow(),
            )
            .returning(IngestionItem.attempt_count)
        )
        count = (await self._session.execute(stmt)).scalar_one()
        return int(count)

    async def insert_processed_event(
        self,
        *,
        event_id: str,
        idempotency_key: str,
        type: str,
        worker_type: str,
        instance_id: str,
        consumed_at: datetime | None = None,
    ) -> InsertOutcome:
        values: dict[str, object] = {
            "event_id": event_id,
            "idempotency_key": idempotency_key,
            "type": type,
            "worker_type": worker_type,
            "instance_id": instance_id,
        }
        if consumed_at is not None:
            values["consumed_at"] = consumed_at
        stmt = (
            insert(ProcessedEvent)
            .values(**values)
            .on_conflict_do_nothing()
            .returning(ProcessedEvent.event_id)
        )
        inserted = (await self._session.execute(stmt)).scalar_one_or_none()
        return InsertOutcome.inserted if inserted is not None else InsertOutcome.duplicate

    async def has_processed_event(
        self,
        *,
        worker_type: str,
        event_id: str,
        idempotency_key: str,
    ) -> bool:
        stmt = (
            select(ProcessedEvent.event_id)
            .where(
                ProcessedEvent.worker_type == worker_type,
                or_(
                    ProcessedEvent.event_id == event_id,
                    ProcessedEvent.idempotency_key == idempotency_key,
                ),
            )
            .limit(1)
        )
        found = (await self._session.execute(stmt)).scalar_one_or_none()
        return found is not None

    async def upsert_heartbeat(
        self,
        *,
        worker_type: str,
        instance_id: str,
        status: str,
        current_subject: str | None,
        processed_ok: int,
        processed_failed: int,
        lag_hint: int | None,
        observed_at: datetime,
    ) -> None:
        stmt = (
            insert(WorkerHeartbeat)
            .values(
                worker_type=worker_type,
                instance_id=instance_id,
                status=status,
                current_subject=current_subject,
                processed_ok=processed_ok,
                processed_failed=processed_failed,
                lag_hint=lag_hint,
                observed_at=observed_at,
            )
            .on_conflict_do_update(
                index_elements=[WorkerHeartbeat.worker_type, WorkerHeartbeat.instance_id],
                set_={
                    "status": status,
                    "current_subject": current_subject,
                    "processed_ok": processed_ok,
                    "processed_failed": processed_failed,
                    "lag_hint": lag_hint,
                    "observed_at": observed_at,
                },
            )
        )
        await self._session.execute(stmt)

    async def list_heartbeats(self) -> tuple[HeartbeatRecord, ...]:
        stmt = select(WorkerHeartbeat).order_by(
            WorkerHeartbeat.worker_type, WorkerHeartbeat.instance_id
        )
        rows = (await self._session.scalars(stmt)).all()
        return tuple(heartbeat_record(row) for row in rows)

    async def counts_by_stage_status(self, process_date: date) -> tuple[StageStatusCount, ...]:
        stmt = (
            select(
                IngestionItem.stage,
                IngestionItem.status,
                func.count().label("count"),
            )
            .where(IngestionItem.process_date == process_date)
            .group_by(IngestionItem.stage, IngestionItem.status)
            .order_by(IngestionItem.stage, IngestionItem.status)
        )
        rows = (await self._session.execute(stmt)).all()
        return tuple(
            StageStatusCount(stage=stage, status=status, count=int(count))
            for stage, status, count in rows
        )

    async def count_parse_errors(self, process_date: date) -> int:
        stmt = select(func.count()).where(
            IngestionItem.process_date == process_date,
            IngestionItem.error_type.in_(("ParseError", "parse_error")),
        )
        count = await self._session.scalar(stmt)
        return int(count or 0)

    async def get_adapter_health(self, adapter_name: str) -> AdapterHealthRecord | None:
        row = await self._session.get(AdapterHealth, adapter_name)
        if row is None:
            return None
        return adapter_health_record(row)

    async def list_adapter_health(self) -> tuple[AdapterHealthRecord, ...]:
        stmt = select(AdapterHealth).order_by(AdapterHealth.adapter_name)
        rows = (await self._session.scalars(stmt)).all()
        return tuple(adapter_health_record(row) for row in rows)

    async def list_items_for_date(self, process_date: date) -> tuple[MonitorItemRecord, ...]:
        stmt = (
            select(IngestionItem, Game.title)
            .outerjoin(Game, Game.metacritic_slug == IngestionItem.metacritic_slug)
            .where(IngestionItem.process_date == process_date)
            .order_by(IngestionItem.run_id, IngestionItem.metacritic_slug, IngestionItem.stage)
        )
        rows = (await self._session.execute(stmt)).all()
        return tuple(
            MonitorItemRecord(
                id=item.id,
                run_id=item.run_id,
                metacritic_slug=item.metacritic_slug,
                title=title,
                stage=IngestionStage(item.stage),
                status=IngestionItemStatus(item.status),
                error_type=item.error_type,
                error_message=item.error_message,
                updated_at=item.updated_at,
            )
            for item, title in rows
        )

    async def monitor_aggregates(self, process_date: date) -> MonitorAggregates:
        return MonitorAggregates(
            heartbeats=await self.list_heartbeats(),
            cursor=await self.get_cursor(process_date),
            runs=await self.list_runs_for_date(process_date),
            stage_counts=await self.counts_by_stage_status(process_date),
            adapter_health=await self.list_adapter_health(),
            parse_error_count=await self.count_parse_errors(process_date),
            items=await self.list_items_for_date(process_date),
        )

    async def upsert_adapter_health(
        self,
        *,
        adapter_name: str,
        circuit_state: str,
        parse_error_streak: int,
        opened_at: datetime | None,
        last_parse_error_at: datetime | None,
    ) -> AdapterHealthRecord:
        now = utcnow()
        stmt = (
            insert(AdapterHealth)
            .values(
                adapter_name=adapter_name,
                circuit_state=circuit_state,
                parse_error_streak=parse_error_streak,
                opened_at=opened_at,
                last_parse_error_at=last_parse_error_at,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AdapterHealth.adapter_name],
                set_={
                    "circuit_state": circuit_state,
                    "parse_error_streak": parse_error_streak,
                    "opened_at": opened_at,
                    "last_parse_error_at": last_parse_error_at,
                    "updated_at": now,
                },
            )
            .returning(AdapterHealth)
        )
        row = (await self._session.scalars(stmt)).one()
        return adapter_health_record(row)

    async def _active_run(
        self, process_date: date, source: str, page: int | None
    ) -> IngestionRun | None:
        stmt = select(IngestionRun).where(
            IngestionRun.process_date == process_date,
            IngestionRun.source == source,
            IngestionRun.status.in_(
                (IngestionRunStatus.requested.value, IngestionRunStatus.running.value)
            ),
        )
        if page is None:
            stmt = stmt.where(IngestionRun.page.is_(None))
        else:
            stmt = stmt.where(IngestionRun.page == page)
        return cast(IngestionRun | None, await self._session.scalar(stmt))
