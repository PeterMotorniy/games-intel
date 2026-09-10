from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.payloads import DeadLetter, DeadLetterReason
from games_intel.db.records import OutboxInsert
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage
from games_intel.kafka.envelope import parse_cloud_event
from games_intel.kafka.exceptions import (
    LlmStructureError,
    NotFoundError,
    ParseError,
    QuotaError,
    SchemaError,
    TransientError,
)
from games_intel.kafka.logging import (
    configure_process_logging,
    emit_json,
    sanitize_error_message,
)
from games_intel.kafka.retry import backoff_seconds
from games_intel.kafka.serialization import (
    cloud_event_headers,
    cloud_event_to_dict,
    encode_cloud_event,
)
from games_intel.kafka.source import worker_source
from games_intel.kafka.types import IncomingRecord, MessageConsumer, MessageProducer
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.kafka.daemon")

SleepFn = Callable[[float], Awaitable[None]]
_UNPREPARED = object()
_TRANSIENT_DB = (OperationalError, InterfaceError, SATimeoutError, ConnectionError, TimeoutError)


@runtime_checkable
class EventHandler(Protocol):
    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None: ...


@runtime_checkable
class ClaimFilter(Protocol):
    async def should_claim(self, event: CloudEvent[Any]) -> bool: ...


@runtime_checkable
class PreparingHandler(Protocol):
    async def prepare(self, event: CloudEvent[Any]) -> object: ...

    async def persist(
        self, event: CloudEvent[Any], session: AsyncSession, prepared: object
    ) -> None: ...


@runtime_checkable
class TerminalFailureHandler(Protocol):
    async def on_terminal_failure(
        self, event: CloudEvent[Any], session: AsyncSession, exc: BaseException
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class DaemonConfig:
    worker_type: str
    instance_id: str
    stage_name: str
    subscribe_event_key: str
    extra_subscribe_event_keys: tuple[str, ...] = ()
    heartbeat_interval_seconds: int = 10
    lease_seconds: int | None = None


class DaemonLoop:
    def __init__(
        self,
        settings: Settings,
        config: DaemonConfig,
        *,
        consumer: MessageConsumer,
        producer: MessageProducer,
        session_factory: async_sessionmaker[AsyncSession],
        handler: EventHandler,
        sleep: SleepFn | None = None,
    ) -> None:
        self.settings = settings
        self.config = config
        self.consumer = consumer
        self.producer = producer
        self._session_factory = session_factory
        self.handler = handler
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep
        self.processed_ok = 0
        self.processed_failed = 0
        self._status = "idle"
        self._current_subject: str | None = None
        self._last_heartbeat_at: datetime | None = None
        self._transient_attempts: dict[str, int] = {}

    @property
    def expected_type(self) -> str:
        return self.settings.event_name(self.config.subscribe_event_key)

    @property
    def allowed_types(self) -> frozenset[str]:
        keys = (self.config.subscribe_event_key, *self.config.extra_subscribe_event_keys)
        return frozenset(self.settings.event_name(key) for key in keys)

    @property
    def source(self) -> str:
        return worker_source(self.settings, self.config.worker_type)

    async def process_record(self, record: IncomingRecord) -> None:
        try:
            event = parse_cloud_event(record.value, self.settings)
            if event.type not in self.allowed_types:
                raise SchemaError("unexpected event type")
        except SchemaError as exc:
            await self._handle_schema_error(record, exc)
            return
        await self._process_valid_event(record, event)

    async def run(self, stop: asyncio.Event) -> None:
        configure_process_logging()
        await self.consumer.start()
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(stop))
        try:
            while not stop.is_set():
                records = await self.consumer.poll()
                if not records:
                    await self._heartbeat("idle", None)
                    continue
                for record in records:
                    if stop.is_set():
                        break
                    await self.process_record(record)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            await self.consumer.stop()

    async def _process_valid_event(self, record: IncomingRecord, event: CloudEvent[Any]) -> None:
        self._current_subject = event.subject
        await self._heartbeat("running", event.subject)
        while True:
            try:
                duplicate = await self._handle_once(event)
            except TransientError as exc:
                attempts = await self._record_transient_attempt(event, exc)
                self._log(event, error_type=type(exc).__name__, attempt=attempts)
                if attempts >= self.settings.retry.max_attempts:
                    await self._finalize_terminal(
                        event,
                        exc,
                        status=IngestionItemStatus.failed,
                        dlq_reason="timeout",
                        original_topic=record.topic,
                    )
                    await self.consumer.commit(record)
                    self.processed_failed += 1
                    await self._heartbeat("error", event.subject)
                    return
                await self._sleep(backoff_seconds(attempts, self.settings.retry))
                continue
            except NotFoundError as exc:
                await self._finalize_terminal(
                    event,
                    exc,
                    status=IngestionItemStatus.failed,
                    dlq_reason=None,
                    original_topic=record.topic,
                )
                await self.consumer.commit(record)
                self.processed_failed += 1
                await self._heartbeat("error", event.subject)
                return
            except ParseError as exc:
                await self._finalize_terminal(
                    event,
                    exc,
                    status=IngestionItemStatus.failed,
                    dlq_reason="handler",
                    original_topic=record.topic,
                )
                await self.consumer.commit(record)
                self.processed_failed += 1
                await self._heartbeat("error", event.subject)
                return
            except LlmStructureError as exc:
                await self._finalize_terminal(
                    event,
                    exc,
                    status=IngestionItemStatus.failed,
                    dlq_reason="handler",
                    original_topic=record.topic,
                )
                await self.consumer.commit(record)
                self.processed_failed += 1
                await self._heartbeat("error", event.subject)
                return
            except QuotaError as exc:
                await self._finalize_terminal(
                    event,
                    exc,
                    status=IngestionItemStatus.degraded,
                    dlq_reason=None,
                    original_topic=record.topic,
                )
                await self.consumer.commit(record)
                self.processed_ok += 1
                await self._heartbeat("idle", None)
                return
            except Exception as exc:
                await self._finalize_terminal(
                    event,
                    exc,
                    status=IngestionItemStatus.failed,
                    dlq_reason="handler",
                    original_topic=record.topic,
                )
                await self.consumer.commit(record)
                self.processed_failed += 1
                await self._heartbeat("error", event.subject)
                return
            await self.consumer.commit(record)
            if not duplicate:
                self.processed_ok += 1
                self._clear_memory_attempts(event.id)
            await self._heartbeat("idle", None)
            return

    async def _handle_once(self, event: CloudEvent[Any]) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    ingestion = IngestionRepository(session)
                    already = await ingestion.has_processed_event(
                        worker_type=self.config.worker_type,
                        event_id=event.id,
                        idempotency_key=event.idempotencykey,
                    )
                    if already:
                        self._log(event, error_type=None, attempt=0, event_name="duplicate")
                        return True
                    if not await _should_claim(self.handler, event):
                        claimed = True
                    else:
                        claimed = await self._claim_work(ingestion, event)
                    if not claimed:
                        raise TransientError("work leased by another replica")
            prepared = await self._prepare_with_timeout(event)
            async with self._session_factory() as session:
                async with session.begin():
                    ingestion = IngestionRepository(session)
                    outcome = await ingestion.insert_processed_event(
                        event_id=event.id,
                        idempotency_key=event.idempotencykey,
                        type=event.type,
                        worker_type=self.config.worker_type,
                        instance_id=self.config.instance_id,
                    )
                    if outcome.value == "duplicate":
                        self._log(event, error_type=None, attempt=0, event_name="duplicate")
                        return True
                    await _invoke_handler(self.handler, event, session, prepared)
                    return False
        except _TRANSIENT_DB as exc:
            raise TransientError(str(exc)) from exc

    async def _claim_work(self, ingestion: IngestionRepository, event: CloudEvent[Any]) -> bool:
        lease = self.config.lease_seconds
        stage = _stage_or_none(self.config.stage_name)
        run_id = _event_run_id(event)
        slugs = _item_slugs(event)
        if not lease or stage is None or run_id is None or not slugs:
            return True
        process_date = await _resolve_process_date(event, ingestion)
        if process_date is None:
            return True
        for slug in slugs:
            ok = await ingestion.try_claim_item(
                run_id=run_id,
                metacritic_slug=slug,
                process_date=process_date,
                stage=stage,
                instance_id=self.config.instance_id,
                lease_seconds=lease,
                event_id=event.id,
            )
            if not ok:
                return False
        return True

    async def _prepare_with_timeout(self, event: CloudEvent[Any]) -> object:
        timeout = max(float(self.settings.retry.prepare_timeout_seconds), 1.0)
        try:
            return await asyncio.wait_for(_prepare_handler(self.handler, event), timeout=timeout)
        except TimeoutError as exc:
            raise TransientError("prepare timed out") from exc

    async def _handle_schema_error(self, record: IncomingRecord, exc: SchemaError) -> None:
        original_id = _peek_event_id(record.value)
        await self._persist_and_publish_dlq(
            original_topic=record.topic,
            original_id=original_id,
            reason="schema",
            error_type=type(exc).__name__,
            error_message=str(exc),
            run_id=None,
        )
        await self.consumer.commit(record)
        self.processed_failed += 1
        emit_json(
            logger,
            level=logging.ERROR,
            worker=self.config.worker_type,
            stage=self.config.stage_name,
            event_id=original_id,
            error_type=type(exc).__name__,
            attempt=0,
            event="schema_error",
        )
        await self._heartbeat("error", None)

    async def _record_transient_attempt(self, event: CloudEvent[Any], exc: TransientError) -> int:
        run_id = _event_run_id(event)
        stage = _stage_or_none(self.config.stage_name)
        async with self._session_factory() as session:
            async with session.begin():
                ingestion = IngestionRepository(session)
                process_date = await _resolve_process_date(event, ingestion)
                slugs = _item_slugs(event)
                if run_id is None or stage is None or process_date is None or not slugs:
                    return self._bump_memory_attempts(event.id)
                attempts = 0
                for slug in slugs:
                    await ingestion.upsert_item(
                        run_id=run_id,
                        metacritic_slug=slug,
                        process_date=process_date,
                        stage=stage,
                        status=IngestionItemStatus.running,
                        event_id=event.id,
                        error_type=type(exc).__name__,
                        error_message=sanitize_error_message(str(exc)),
                    )
                    item = await ingestion.get_item(run_id, slug, stage)
                    if item is not None:
                        attempts = await ingestion.increment_attempt(item.id)
                return attempts if attempts else self._bump_memory_attempts(event.id)

    def _bump_memory_attempts(self, event_id: str) -> int:
        attempts = self._transient_attempts.get(event_id, 0) + 1
        self._transient_attempts[event_id] = attempts
        return attempts

    def _clear_memory_attempts(self, event_id: str) -> None:
        self._transient_attempts.pop(event_id, None)

    async def _finalize_terminal(
        self,
        event: CloudEvent[Any],
        exc: BaseException,
        *,
        status: IngestionItemStatus,
        dlq_reason: DeadLetterReason | None,
        original_topic: str | None = None,
    ) -> None:
        run_id = _event_run_id(event)
        stage = _stage_or_none(self.config.stage_name)
        dlq_event = None
        async with self._session_factory() as session:
            async with session.begin():
                ingestion = IngestionRepository(session)
                process_date = await _resolve_process_date(event, ingestion)
                await ingestion.insert_processed_event(
                    event_id=event.id,
                    idempotency_key=event.idempotencykey,
                    type=event.type,
                    worker_type=self.config.worker_type,
                    instance_id=self.config.instance_id,
                )
                if run_id is not None and stage is not None and process_date is not None:
                    slugs = _item_slugs(event)
                    for slug in slugs:
                        await ingestion.upsert_item(
                            run_id=run_id,
                            metacritic_slug=slug,
                            process_date=process_date,
                            stage=stage,
                            status=status,
                            event_id=event.id,
                            error_type=type(exc).__name__,
                            error_message=sanitize_error_message(str(exc)),
                        )
                await _call_terminal_failure(self.handler, event, session, exc)
                if dlq_reason is not None:
                    dlq_event = _build_dlq_event(
                        self.settings,
                        source=self.source,
                        original_topic=original_topic or self.expected_type,
                        original_id=event.id,
                        reason=dlq_reason,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        run_id=run_id,
                    )
                    await _insert_dlq_outbox(session, self.config.worker_type, dlq_event)
        self._log(event, error_type=type(exc).__name__, attempt=None, event_name="terminal")
        self._clear_memory_attempts(event.id)
        if dlq_event is not None:
            await self._publish_dlq_best_effort(dlq_event)

    async def _persist_and_publish_dlq(
        self,
        *,
        original_topic: str,
        original_id: str,
        reason: DeadLetterReason,
        error_type: str,
        error_message: str,
        run_id: UUID | None,
    ) -> None:
        event = _build_dlq_event(
            self.settings,
            source=self.source,
            original_topic=original_topic,
            original_id=original_id,
            reason=reason,
            error_type=error_type,
            error_message=error_message,
            run_id=run_id,
        )
        async with self._session_factory() as session:
            async with session.begin():
                await _insert_dlq_outbox(session, self.config.worker_type, event)
        await self._publish_dlq_best_effort(event)

    async def _publish_dlq_best_effort(self, event: CloudEvent[Any]) -> None:
        try:
            await self.producer.send(
                topic=self.settings.event_name("dlq"),
                key=event.subject,
                value=encode_cloud_event(event),
                headers=cloud_event_headers(),
            )
        except Exception:
            emit_json(
                logger,
                level=logging.ERROR,
                worker=self.config.worker_type,
                stage="dlq",
                event_id=event.id,
                event="dlq_produce_failed",
            )
            return
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await OutboxRepository(session).mark_published_by_key(event.idempotencykey)
        except Exception:
            emit_json(
                logger,
                level=logging.WARNING,
                worker=self.config.worker_type,
                stage="dlq",
                event_id=event.id,
                event="dlq_mark_published_failed",
            )

    async def _heartbeat_loop(self, stop: asyncio.Event) -> None:
        interval = max(float(self.config.heartbeat_interval_seconds), 1.0)
        while not stop.is_set():
            await self._heartbeat(self._status, self._current_subject, force=True)
            await self._sleep(interval)

    async def _heartbeat(
        self,
        status: str,
        subject: str | None,
        *,
        force: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        changed = status != self._status or subject != self._current_subject
        self._status = status
        self._current_subject = subject
        interval = max(self.config.heartbeat_interval_seconds, 1)
        if (
            not force
            and not changed
            and self._last_heartbeat_at is not None
            and (now - self._last_heartbeat_at).total_seconds() < interval
        ):
            return
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await IngestionRepository(session).upsert_heartbeat(
                        worker_type=self.config.worker_type,
                        instance_id=self.config.instance_id,
                        status=status,
                        current_subject=subject,
                        processed_ok=self.processed_ok,
                        processed_failed=self.processed_failed,
                        lag_hint=None,
                        observed_at=now,
                    )
        except Exception as exc:
            emit_json(
                logger,
                level=logging.WARNING,
                worker=self.config.worker_type,
                stage=self.config.stage_name,
                error_type=type(exc).__name__,
                event="heartbeat_failed",
            )
            return
        self._last_heartbeat_at = now

    def _log(
        self,
        event: CloudEvent[Any],
        *,
        error_type: str | None,
        attempt: int | None,
        event_name: str = "handle",
    ) -> None:
        emit_json(
            logger,
            run_id=str(event.runid) if event.runid is not None else None,
            slug=event.subject,
            worker=self.config.worker_type,
            stage=self.config.stage_name,
            event_id=event.id,
            error_type=error_type,
            attempt=attempt,
            event=event_name,
        )


async def _should_claim(handler: EventHandler, event: CloudEvent[Any]) -> bool:
    if isinstance(handler, ClaimFilter):
        return await handler.should_claim(event)
    return True


async def _prepare_handler(handler: EventHandler, event: CloudEvent[Any]) -> object:
    if isinstance(handler, PreparingHandler):
        return await handler.prepare(event)
    return _UNPREPARED


async def _invoke_handler(
    handler: EventHandler,
    event: CloudEvent[Any],
    session: AsyncSession,
    prepared: object,
) -> None:
    if prepared is not _UNPREPARED and isinstance(handler, PreparingHandler):
        await handler.persist(event, session, prepared)
        return
    await handler.handle(event, session)


async def _call_terminal_failure(
    handler: EventHandler,
    event: CloudEvent[Any],
    session: AsyncSession,
    exc: BaseException,
) -> None:
    if isinstance(handler, TerminalFailureHandler):
        await handler.on_terminal_failure(event, session, exc)


def _stage_or_none(stage_name: str) -> IngestionStage | None:
    try:
        return IngestionStage(stage_name)
    except ValueError:
        return None


def _item_slugs(event: CloudEvent[Any]) -> tuple[str, ...]:
    """Game slugs affected by this event. Page listings must not use run_id as slug."""
    data = event.data
    games = getattr(data, "games", None)
    if isinstance(games, list | tuple):
        slugs = tuple(
            slug
            for game in games
            if isinstance((slug := getattr(game, "metacritic_slug", None)), str) and slug
        )
        if slugs:
            return slugs
    slug = getattr(data, "metacritic_slug", None)
    if isinstance(slug, str) and slug:
        return (slug,)
    nested = getattr(data, "game", None)
    nested_slug = getattr(nested, "metacritic_slug", None)
    if isinstance(nested_slug, str) and nested_slug:
        return (nested_slug,)
    subject = event.subject
    run_id = _event_run_id(event)
    if isinstance(subject, str) and subject and (run_id is None or subject != str(run_id)):
        return (subject,)
    return ()


def _event_run_id(event: CloudEvent[Any]) -> UUID | None:
    if event.runid is not None:
        return event.runid
    data = event.data
    run_id = getattr(data, "run_id", None)
    return run_id if isinstance(run_id, UUID) else None


def _event_process_date(event: CloudEvent[Any]) -> date | None:
    process_date = getattr(event.data, "process_date", None)
    return process_date if isinstance(process_date, date) else None


async def _resolve_process_date(
    event: CloudEvent[Any], ingestion: IngestionRepository
) -> date | None:
    process_date = _event_process_date(event)
    if process_date is not None:
        return process_date
    run_id = _event_run_id(event)
    if run_id is None:
        return None
    run = await ingestion.get_run(run_id)
    return None if run is None else run.process_date


def _peek_event_id(value: bytes) -> str:
    try:
        raw: object = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "invalid"
    if isinstance(raw, dict) and isinstance(raw.get("id"), str) and raw["id"]:
        return str(raw["id"])
    return "invalid"


def _build_dlq_event(
    settings: Settings,
    *,
    source: str,
    original_topic: str,
    original_id: str,
    reason: DeadLetterReason,
    error_type: str,
    error_message: str,
    run_id: UUID | None,
) -> CloudEvent[Any]:
    dead = DeadLetter(
        original_topic=original_topic,
        original_id=original_id,
        reason=reason,
        error_type=error_type,
        error_message=sanitize_error_message(error_message),
        payload_truncated=True,
    )
    return build_cloud_event(
        settings,
        "dlq",
        source=source,
        subject=original_id or original_topic,
        data=dead,
        stage="dlq",
        run_id=run_id,
    )


async def _insert_dlq_outbox(
    session: AsyncSession, worker_type: str, event: CloudEvent[Any]
) -> None:
    await OutboxRepository(session).insert(
        OutboxInsert(
            producer=worker_type,
            idempotency_key=event.idempotencykey,
            topic=event.type,
            partition_key=event.subject,
            payload=cloud_event_to_dict(event),
        )
    )
