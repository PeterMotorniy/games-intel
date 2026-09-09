from __future__ import annotations

import re

_ISO8601 = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
    re.ASCII,
)


def parse_iso8601_duration(value: str) -> int | None:
    """YouTube contentDetails.duration → seconds. Invalid input is None, not zero."""

    match = _ISO8601.fullmatch(value.strip())
    if match is None:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86_400 + hours * 3_600 + minutes * 60 + seconds
