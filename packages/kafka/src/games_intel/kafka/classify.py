from __future__ import annotations

from games_intel.contracts.adapters import AdapterError
from games_intel.kafka.exceptions import (
    NotFoundError,
    ParseError,
    QuotaError,
    TransientError,
)

_TRANSIENT_CODES = frozenset({"timeout", "rate_limited", "unavailable", "circuit_open"})


def map_adapter_error(
    error: AdapterError,
) -> TransientError | NotFoundError | ParseError | QuotaError:
    if error.code in _TRANSIENT_CODES:
        return TransientError(error.message)
    if error.code == "not_found":
        return NotFoundError(error.message)
    if error.code == "parse_error":
        return ParseError(error.message)
    if error.code == "quota_exceeded":
        return QuotaError(error.message)
    msg = f"unmapped adapter error code: {error.code}"
    raise TransientError(msg)
