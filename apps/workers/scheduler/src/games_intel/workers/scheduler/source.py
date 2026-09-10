from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from games_intel.db.records import IngestionCursorRecord
from games_intel.db.types import IngestionRunStatus
from games_intel.settings import Settings

_CLAIMED = frozenset(
    {
        IngestionRunStatus.requested,
        IngestionRunStatus.running,
        IngestionRunStatus.completed,
    }
)


class PageClaim(Protocol):
    @property
    def source(self) -> str: ...

    @property
    def page(self) -> int | None: ...

    @property
    def status(self) -> IngestionRunStatus: ...


def decide_source_and_page(
    cursor: IngestionCursorRecord | None,
    settings: Settings,
    runs: Sequence[PageClaim] = (),
) -> tuple[str, int | None]:
    """Same page rule for cron and manual: new_releases once, then browse last+1.

    In-flight and completed runs reserve a page so the next tick (manual or
    scheduled) opens the following page instead of duplicating the current one.
    Failed runs do not reserve: the same page is retried.
    """
    new_releases = settings.scheduler.new_releases_source
    browse = settings.scheduler.browse_source
    new_releases_claimed = any(
        run.source == new_releases and run.status in _CLAIMED for run in runs
    )
    if not new_releases_claimed and (cursor is None or not cursor.new_releases_done):
        return new_releases, None

    last_page = 0
    if cursor is not None and cursor.last_browse_page is not None:
        last_page = cursor.last_browse_page
    for run in runs:
        if run.source != browse or run.status not in _CLAIMED or run.page is None:
            continue
        if run.page > last_page:
            last_page = run.page
    return browse, last_page + 1
