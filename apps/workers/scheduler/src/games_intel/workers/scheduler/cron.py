from __future__ import annotations

from datetime import datetime


def cron_matches(expression: str, when: datetime) -> bool:
    """Match a 5-field cron (minute hour day month weekday). weekday 0 = Sunday."""
    fields = expression.split()
    if len(fields) != 5:
        msg = f"expected 5-field cron, got {expression!r}"
        raise ValueError(msg)
    minute, hour, day, month, weekday = fields
    cron_weekday = (when.weekday() + 1) % 7
    return (
        _field_matches(minute, when.minute, 0, 59)
        and _field_matches(hour, when.hour, 0, 23)
        and _field_matches(day, when.day, 1, 31)
        and _field_matches(month, when.month, 1, 12)
        and _field_matches(weekday, cron_weekday, 0, 6)
    )


def _field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    for part in field.split(","):
        token = part.strip()
        if not token:
            continue
        if token == "*":
            return True
        if token.startswith("*/"):
            step = int(token[2:])
            if step <= 0:
                msg = f"invalid cron step: {token}"
                raise ValueError(msg)
            if value % step == 0:
                return True
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if start < minimum or end > maximum or start > end:
                msg = f"invalid cron range: {token}"
                raise ValueError(msg)
            if start <= value <= end:
                return True
            continue
        if int(token) == value:
            return True
    return False


class CronMinuteGate:
    """Fire at most once per matching wall-clock minute so a 1s poll cannot duplicate."""

    def __init__(self) -> None:
        self._last: tuple[int, int, int, int, int] | None = None

    def due(self, expression: str, when: datetime) -> bool:
        if not cron_matches(expression, when):
            return False
        key = (when.year, when.month, when.day, when.hour, when.minute)
        if self._last == key:
            return False
        self._last = key
        return True
