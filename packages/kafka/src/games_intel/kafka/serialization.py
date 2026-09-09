from __future__ import annotations

import json
from typing import Any

from games_intel.contracts.envelope import CloudEvent

CLOUDEVENTS_CONTENT_TYPE = "application/cloudevents+json"
CONTENT_TYPE_HEADER = ("content-type", CLOUDEVENTS_CONTENT_TYPE.encode("utf-8"))


def cloud_event_to_dict(event: CloudEvent[Any]) -> dict[str, Any]:
    return event.model_dump(mode="json")


def encode_cloud_event(event: CloudEvent[Any]) -> bytes:
    return json.dumps(cloud_event_to_dict(event), separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def encode_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def cloud_event_headers() -> tuple[tuple[str, bytes], ...]:
    return (CONTENT_TYPE_HEADER,)
