from __future__ import annotations

from games_intel.contracts.adapters import AdapterError
from games_intel.kafka.classify import map_adapter_error
from games_intel.kafka.exceptions import NotFoundError, ParseError, QuotaError, TransientError


def test_adapter_error_mapping() -> None:
    assert isinstance(map_adapter_error(AdapterError(code="timeout", message="t")), TransientError)
    assert isinstance(
        map_adapter_error(AdapterError(code="rate_limited", message="r")), TransientError
    )
    assert isinstance(
        map_adapter_error(AdapterError(code="unavailable", message="u")), TransientError
    )
    assert isinstance(
        map_adapter_error(AdapterError(code="circuit_open", message="c")), TransientError
    )
    assert isinstance(map_adapter_error(AdapterError(code="not_found", message="n")), NotFoundError)
    assert isinstance(map_adapter_error(AdapterError(code="parse_error", message="p")), ParseError)
    assert isinstance(
        map_adapter_error(AdapterError(code="quota_exceeded", message="q")), QuotaError
    )
