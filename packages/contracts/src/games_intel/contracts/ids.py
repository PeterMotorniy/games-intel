from __future__ import annotations

import secrets
import time
import uuid
from uuid import UUID


def uuid7() -> UUID:
    factory = getattr(uuid, "uuid7", None)
    if callable(factory):
        generated = factory()
        if isinstance(generated, UUID):
            return generated
    return _uuid7_rfc9562()


def new_event_id() -> str:
    return str(uuid7())


def new_traceparent() -> str:
    """W3C traceparent for a new root trace (one Kafka task = one trace)."""
    trace_id = uuid7().hex
    span_id = secrets.token_hex(8)
    return f"00-{trace_id}-{span_id}-01"


def _uuid7_rfc9562() -> UUID:
    unix_ts_ms = time.time_ns() // 1_000_000 & 0xFFFFFFFFFFFF
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    uuid_int = (unix_ts_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=uuid_int)
