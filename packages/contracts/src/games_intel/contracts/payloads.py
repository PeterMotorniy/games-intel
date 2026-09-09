from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, HttpUrl

_STRICT = ConfigDict(extra="forbid")


def _tbd_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower().rstrip(".") == "tbd":
        return None
    return value


Metascore = Annotated[int | None, BeforeValidator(_tbd_to_none)]
Userscore = Annotated[float | None, BeforeValidator(_tbd_to_none)]

Trigger = Literal["cron", "manual"]
RunSource = Literal["new_releases", "browse"]
LetsPlayStatus = Literal["ok", "no_video", "transcript_unavailable", "quota_exceeded"]
WorkerStatus = Literal["idle", "running", "error"]
DeadLetterReason = Literal["schema", "handler", "timeout"]
RecomputeScope = Literal["game", "neighbors", "all"]
RecomputeReason = Literal["cataloged", "reviews", "schedule", "manual"]


class ScheduleTick(BaseModel):
    model_config = _STRICT

    trigger: Trigger
    requested_at: datetime
    process_date: date


class RunRequested(BaseModel):
    model_config = _STRICT

    run_id: UUID
    process_date: date
    source: RunSource
    page: int | None = None
    limit: int = Field(default=20, ge=1)
    trigger: Trigger


class ListedGame(BaseModel):
    model_config = _STRICT

    metacritic_slug: str
    title: str
    listing_url: HttpUrl
    position: int = Field(ge=0)


class GamesPageListed(BaseModel):
    """One listing page: Catalog loads all cards in a single task/trace."""

    model_config = _STRICT

    run_id: UUID
    process_date: date
    source: RunSource
    page: int | None = None
    games: list[ListedGame] = Field(default_factory=list)


class PlatformScore(BaseModel):
    model_config = _STRICT

    platform_code: str
    metascore: Metascore = None
    userscore: Userscore = None


class GameCataloged(BaseModel):
    model_config = _STRICT

    run_id: UUID
    process_date: date
    metacritic_slug: str
    title: str
    cover_url: str | None = None
    cover_source_url: HttpUrl | None = None
    developer: str | None = None
    publisher: str | None = None
    genres: list[str] = Field(default_factory=list)
    release_date: date | None = None
    description: str | None = None
    video_url: HttpUrl | None = None
    platforms: list[PlatformScore] = Field(default_factory=list)


class ReviewSummary(BaseModel):
    model_config = _STRICT

    likes: list[str]
    dislikes: list[str]
    summary: str


class GameReviewsSummarized(BaseModel):
    model_config = _STRICT

    run_id: UUID
    metacritic_slug: str
    critic: ReviewSummary
    user: ReviewSummary
    critic_review_count: int = Field(ge=0)
    user_review_count: int = Field(ge=0)
    degraded: bool


class GameLetsPlayAnalyzed(BaseModel):
    model_config = _STRICT

    run_id: UUID
    metacritic_slug: str
    status: LetsPlayStatus
    video_url: HttpUrl | None = None
    video_title: str | None = None
    view_count: int | None = Field(default=None, ge=0)
    conclusion: str | None = None
    highlights: list[str] = Field(default_factory=list)


class SimilarGameRef(BaseModel):
    model_config = _STRICT

    metacritic_slug: str
    title: str
    score: float
    rank: int = Field(ge=1)


class GameSimilarAssigned(BaseModel):
    model_config = _STRICT

    run_id: UUID
    metacritic_slug: str
    items: list[SimilarGameRef]


class SimilarityRecomputeRequested(BaseModel):
    model_config = _STRICT

    run_id: UUID | None = None
    process_date: date
    scope: RecomputeScope
    center_slug: str | None = None
    candidate_slugs: list[str] = Field(default_factory=list)
    reason: RecomputeReason


class WorkerHeartbeat(BaseModel):
    model_config = _STRICT

    worker_type: str
    instance_id: str
    status: WorkerStatus
    current_subject: str | None = None
    processed_ok: int = Field(ge=0)
    processed_failed: int = Field(ge=0)
    lag_hint: int | None = None
    observed_at: datetime


class DeadLetter(BaseModel):
    model_config = _STRICT

    original_topic: str
    original_id: str
    reason: DeadLetterReason
    error_type: str
    error_message: str
    payload_truncated: bool
