from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from games_intel.contracts.payloads import (
    LetsPlayStatus,
    PlatformScore,
    ReviewSummary,
    SimilarGameRef,
)

_STRICT = ConfigDict(extra="forbid")

GameSortName = Literal["metascore", "userscore", "title", "updated"]
SortOrderName = Literal["asc", "desc"]


class ProblemDetails(BaseModel):
    model_config = _STRICT

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


class PaginationMeta(BaseModel):
    model_config = _STRICT

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    sort: GameSortName
    order: SortOrderName


CollectionStatusName = Literal["idle", "loading", "empty", "error", "ready"]


class CollectionStateRead(BaseModel):
    model_config = _STRICT

    status: CollectionStatusName
    error_type: str | None = None
    error_message: str | None = None


class GameHydrationRead(BaseModel):
    model_config = _STRICT

    catalog: CollectionStateRead
    critic: CollectionStateRead
    user: CollectionStateRead
    letsplay: CollectionStateRead
    similar: CollectionStateRead


class GameListItemRead(BaseModel):
    model_config = _STRICT

    metacritic_slug: str
    title: str
    cover_url: str | None = None
    developer: str | None = None
    metascore: int | None = None
    userscore: float | None = None
    platforms: list[str] = Field(default_factory=list)
    updated_at: datetime
    catalog_collection: CollectionStateRead


class GameListResponse(BaseModel):
    model_config = _STRICT

    items: list[GameListItemRead]
    meta: PaginationMeta


class LetsPlayRead(BaseModel):
    model_config = _STRICT

    status: LetsPlayStatus | None = None
    video_url: str | None = None
    video_title: str | None = None
    view_count: int | None = Field(default=None, ge=0)
    conclusion: str | None = None
    highlights: list[str] | None = None


class GameCardRead(BaseModel):
    model_config = _STRICT

    metacritic_slug: str
    title: str
    cover_url: str | None = None
    developer: str | None = None
    publisher: str | None = None
    description: str | None = None
    video_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    release_date: date | None = None
    platforms: list[PlatformScore] = Field(default_factory=list)
    critic: ReviewSummary | None = None
    user: ReviewSummary | None = None
    letsplay: LetsPlayRead | None = None
    similar: list[SimilarGameRef] = Field(default_factory=list)
    hydration: GameHydrationRead


class PlatformListResponse(BaseModel):
    model_config = _STRICT

    items: list[str]


class LivenessResponse(BaseModel):
    model_config = _STRICT

    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    model_config = _STRICT

    status: Literal["ok"] = "ok"
    postgres: bool
    kafka: bool | None = None


WorkerStatusName = Literal["idle", "running", "error"]
CircuitStateName = Literal["closed", "open", "half_open"]
IngestionRunStatusName = Literal["requested", "running", "completed", "failed"]
RunTriggerName = Literal["cron", "manual"]
IngestionItemStatusName = Literal["pending", "running", "completed", "failed", "degraded"]
IngestionStageName = Literal["discovered", "cataloged", "reviews", "letsplay", "similar"]


class WorkerHeartbeatRead(BaseModel):
    model_config = _STRICT

    worker_type: str
    instance_id: str
    status: WorkerStatusName
    current_subject: str | None = None
    processed_ok: int = Field(ge=0)
    processed_failed: int = Field(ge=0)
    lag_hint: int | None = None
    observed_at: datetime
    stale: bool


class MonitorRunRead(BaseModel):
    model_config = _STRICT

    id: UUID
    process_date: date
    source: str
    page: int | None = None
    limit: int
    trigger: RunTriggerName
    status: IngestionRunStatusName
    discovered_count: int = Field(ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MonitorItemRead(BaseModel):
    model_config = _STRICT

    id: UUID
    run_id: UUID
    metacritic_slug: str
    title: str | None = None
    stage: IngestionStageName
    status: IngestionItemStatusName
    error_type: str | None = None
    error_message: str | None = None
    updated_at: datetime


class StageStatusCountRead(BaseModel):
    model_config = _STRICT

    stage: str
    status: str
    count: int = Field(ge=0)


class MonitorCursorRead(BaseModel):
    model_config = _STRICT

    process_date: date
    new_releases_done: bool
    last_browse_page: int | None = None


class MonitorScrapeRead(BaseModel):
    model_config = _STRICT

    circuit_state: CircuitStateName | None = None
    last_parse_error_at: datetime | None = None
    parse_error_count: int = Field(ge=0)


class MonitorSnapshot(BaseModel):
    model_config = _STRICT

    process_date: date
    workers: list[WorkerHeartbeatRead]
    runs: list[MonitorRunRead]
    items: list[MonitorItemRead]
    counts: list[StageStatusCountRead]
    cursor: MonitorCursorRead | None = None
    scrape: MonitorScrapeRead


class RunAcceptedResponse(BaseModel):
    model_config = _STRICT

    status: Literal["run_accepted"] = "run_accepted"
    process_date: date
