from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.registry import payload_model_for_event_key
from games_intel.kafka.exceptions import SchemaError
from games_intel.settings import Settings


def event_key_for_type(settings: Settings, event_type: str) -> str:
    for key in type(settings.kafka.events).model_fields:
        if settings.event_name(key) == event_type:
            return key
    msg = f"unknown event type: {event_type}"
    raise KeyError(msg)


def parse_cloud_event(
    value: bytes,
    settings: Settings,
    *,
    expected_type: str | None = None,
) -> CloudEvent[Any]:
    try:
        raw: object = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaError("invalid cloud event json") from exc
    if not isinstance(raw, dict):
        raise SchemaError("cloud event must be an object")
    try:
        envelope = CloudEvent[dict[str, Any]].model_validate(raw)
    except ValidationError as exc:
        raise SchemaError("invalid cloud event envelope") from exc
    if expected_type is not None and envelope.type != expected_type:
        raise SchemaError("unexpected event type")
    try:
        event_key = event_key_for_type(settings, envelope.type)
    except KeyError as exc:
        raise SchemaError("unknown event type") from exc
    payload_cls = payload_model_for_event_key(event_key)
    try:
        data = payload_cls.model_validate(envelope.data)
    except ValidationError as exc:
        raise SchemaError("invalid event data") from exc
    return envelope.model_copy(update={"data": data})
