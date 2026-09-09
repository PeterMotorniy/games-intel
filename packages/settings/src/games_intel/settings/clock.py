from __future__ import annotations

from datetime import UTC, date, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from games_intel.settings.config import Settings

_UTC_ALIASES = frozenset({"UTC", "Etc/UTC", "GMT"})


def process_date_for(settings: Settings, when: datetime | None = None) -> date:
    """Calendar day of the listing window in `app.process_timezone`."""
    instant = when if when is not None else datetime.now(UTC)
    if instant.tzinfo is None or instant.utcoffset() is None:
        instant = instant.replace(tzinfo=UTC)
    name = settings.app.process_timezone
    zone: tzinfo
    if name in _UTC_ALIASES:
        zone = UTC
    else:
        try:
            zone = ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            msg = f"unknown app.process_timezone: {name}"
            raise ValueError(msg) from exc
    return instant.astimezone(zone).date()
