from __future__ import annotations

from games_intel.adapters.youtube.duration import parse_iso8601_duration


def test_parses_hours_minutes_seconds() -> None:
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration("PT3M") == 180
    assert parse_iso8601_duration("PT180S") == 180
    assert parse_iso8601_duration("PT1M30S") == 90


def test_invalid_duration_is_none() -> None:
    assert parse_iso8601_duration("not-a-duration") is None
    assert parse_iso8601_duration("") is None
