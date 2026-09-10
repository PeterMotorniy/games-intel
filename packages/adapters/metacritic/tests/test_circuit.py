from __future__ import annotations

from datetime import UTC, datetime, timedelta

from games_intel.adapters.metacritic.circuit import CircuitBreaker


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def test_circuit_opens_after_threshold() -> None:
    clock = FakeClock(datetime(2026, 9, 8, tzinfo=UTC))
    breaker = CircuitBreaker(
        fail_threshold=3,
        open_seconds=600,
        clock=clock,
    )
    breaker.record_parse_error()
    breaker.record_parse_error()
    assert breaker.snapshot.state == "closed"
    breaker.record_parse_error()
    assert breaker.snapshot.state == "open"
    assert breaker.allow_request() is False


def test_half_open_success_closes() -> None:
    clock = FakeClock(datetime(2026, 9, 8, tzinfo=UTC))
    breaker = CircuitBreaker(
        fail_threshold=2,
        open_seconds=10,
        clock=clock,
    )
    breaker.record_parse_error()
    breaker.record_parse_error()
    assert breaker.snapshot.state == "open"
    clock.advance(10)
    assert breaker.allow_request() is True
    assert breaker.snapshot.state == "half_open"
    breaker.record_success()
    assert breaker.snapshot.state == "closed"


def test_half_open_parse_error_reopens() -> None:
    clock = FakeClock(datetime(2026, 9, 8, tzinfo=UTC))
    breaker = CircuitBreaker(
        fail_threshold=1,
        open_seconds=5,
        clock=clock,
    )
    breaker.record_parse_error()
    clock.advance(5)
    assert breaker.allow_request() is True
    assert breaker.allow_request() is False
    breaker.record_parse_error()
    assert breaker.snapshot.state == "open"
    assert breaker.allow_request() is False


def test_half_open_timeout_reopens() -> None:
    clock = FakeClock(datetime(2026, 9, 8, tzinfo=UTC))
    breaker = CircuitBreaker(fail_threshold=1, open_seconds=5, clock=clock)
    breaker.record_parse_error()
    clock.advance(5)
    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.snapshot.state == "open"
