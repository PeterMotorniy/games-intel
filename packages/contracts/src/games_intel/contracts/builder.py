from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.ids import new_event_id
from games_intel.contracts.registry import payload_model_for_event_key
from games_intel.settings import Settings


def format_idempotency_key(
    template: str,
    *,
    event_type: str,
    run_id: str,
    subject: str,
    stage: str,
) -> str:
    return template.format(
        event_type=event_type,
        run_id=run_id,
        subject=subject,
        stage=stage,
    )


def build_cloud_event(
    settings: Settings,
    event_key: str,
    *,
    source: str,
    subject: str,
    data: BaseModel,
    stage: str,
    run_id: UUID | str | None = None,
    event_id: str | None = None,
    dataschema: str | None = None,
    traceparent: str | None = None,
    occurred_at: datetime | None = None,
    idempotency_key: str | None = None,
) -> CloudEvent[Any]:
    payload_cls = payload_model_for_event_key(event_key)
    if not isinstance(data, payload_cls):
        msg = f"data must be {payload_cls.__name__} for event key {event_key}"
        raise TypeError(msg)
    event_type = settings.event_name(event_key)
    run_id_str = "" if run_id is None else str(run_id)
    idempotencykey = idempotency_key or format_idempotency_key(
        settings.idempotency.key_template,
        event_type=event_type,
        run_id=run_id_str,
        subject=subject,
        stage=stage,
    )
    schema = dataschema or f"https://games-intel.local/schemas/{payload_cls.__name__}.json"
    event_time = occurred_at or datetime.now(UTC)
    run_uuid: UUID | None
    if run_id is None:
        run_uuid = None
    elif isinstance(run_id, UUID):
        run_uuid = run_id
    else:
        run_uuid = UUID(run_id)
    return CloudEvent[Any](
        specversion="1.0",
        id=event_id or new_event_id(),
        source=source,
        type=event_type,
        time=event_time,
        dataschema=schema,
        subject=subject,
        idempotencykey=idempotencykey,
        data=data,
        runid=run_uuid,
        traceparent=traceparent,
    )
