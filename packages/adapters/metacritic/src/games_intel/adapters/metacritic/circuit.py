from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        from datetime import UTC

        return datetime.now(UTC)


@dataclass
class CircuitSnapshot:
    state: str
    parse_error_streak: int = 0
    opened_at: datetime | None = None
    last_parse_error_at: datetime | None = None


class CircuitBreaker:
    def __init__(
        self,
        *,
        fail_threshold: int,
        open_seconds: int,
        clock: Clock | None = None,
        initial: CircuitSnapshot | None = None,
    ) -> None:
        self._fail_threshold = fail_threshold
        self._open_seconds = open_seconds
        self._clock = clock if clock is not None else SystemClock()
        self._half_open_probe = False
        self._snapshot = initial or CircuitSnapshot(state="closed")

    @property
    def snapshot(self) -> CircuitSnapshot:
        return CircuitSnapshot(
            state=self._snapshot.state,
            parse_error_streak=self._snapshot.parse_error_streak,
            opened_at=self._snapshot.opened_at,
            last_parse_error_at=self._snapshot.last_parse_error_at,
        )

    def allow_request(self) -> bool:
        if self._snapshot.state == "closed":
            return True
        if self._snapshot.state == "half_open":
            if self._half_open_probe:
                return False
            self._half_open_probe = True
            return True
        opened_at = self._snapshot.opened_at
        if opened_at is None:
            return False
        if self._clock.now() - opened_at >= timedelta(seconds=self._open_seconds):
            self._snapshot.state = "half_open"
            self._half_open_probe = True
            return True
        return False

    def record_success(self) -> CircuitSnapshot:
        self._half_open_probe = False
        self._snapshot.state = "closed"
        self._snapshot.parse_error_streak = 0
        self._snapshot.opened_at = None
        return self.snapshot

    def record_failure(self) -> CircuitSnapshot:
        """Timeout / unavailable / rate-limit in half-open re-opens; closed stays closed."""
        now = self._clock.now()
        if self._snapshot.state == "half_open":
            self._half_open_probe = False
            self._snapshot.state = "open"
            self._snapshot.opened_at = now
            return self.snapshot
        return self.snapshot

    def record_parse_error(self) -> CircuitSnapshot:
        now = self._clock.now()
        self._snapshot.last_parse_error_at = now
        if self._snapshot.state == "half_open":
            self._half_open_probe = False
            self._snapshot.state = "open"
            self._snapshot.opened_at = now
            self._snapshot.parse_error_streak = max(self._snapshot.parse_error_streak, 1)
            return self.snapshot
        self._snapshot.parse_error_streak += 1
        if self._snapshot.parse_error_streak >= self._fail_threshold:
            self._snapshot.state = "open"
            self._snapshot.opened_at = now
        return self.snapshot
