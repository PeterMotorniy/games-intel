from __future__ import annotations

from enum import Enum, StrEnum


class InsertOutcome(StrEnum):
    inserted = "inserted"
    duplicate = "duplicate"


class LetsPlayStatus(StrEnum):
    ok = "ok"
    no_video = "no_video"
    transcript_unavailable = "transcript_unavailable"
    quota_exceeded = "quota_exceeded"


class IngestionStage(StrEnum):
    discovered = "discovered"
    cataloged = "cataloged"
    reviews = "reviews"
    letsplay = "letsplay"
    similar = "similar"


class IngestionItemStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    degraded = "degraded"


class IngestionRunStatus(StrEnum):
    requested = "requested"
    running = "running"
    completed = "completed"
    failed = "failed"


class RunTrigger(StrEnum):
    cron = "cron"
    manual = "manual"


class GameSort(Enum):
    metascore = "metascore"
    userscore = "userscore"
    title = "title"
    updated = "updated"


class SortOrder(StrEnum):
    asc = "asc"
    desc = "desc"
