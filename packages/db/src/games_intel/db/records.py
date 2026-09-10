from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from games_intel.db.types import (
    GameSort,
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionStage,
    InsertOutcome,
    LetsPlayStatus,
    RunTrigger,
    SortOrder,
)


@dataclass(frozen=True, slots=True)
class PlatformScoreRecord:
    platform_code: str
    metascore: int | None = None
    userscore: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CatalogSlice:
    metacritic_slug: str
    title: str
    listing_url: str | None = None
    cover_url: str | None = None
    cover_source_url: str | None = None
    developer: str | None = None
    publisher: str | None = None
    genres: tuple[str, ...] = ()
    release_date: date | None = None
    description: str | None = None
    video_url: str | None = None
    platforms: tuple[PlatformScoreRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewsSlice:
    metacritic_slug: str
    critic_likes: tuple[str, ...] | None
    critic_dislikes: tuple[str, ...] | None
    critic_summary: str | None
    user_likes: tuple[str, ...] | None
    user_dislikes: tuple[str, ...] | None
    user_summary: str | None


@dataclass(frozen=True, slots=True)
class LetsPlaySlice:
    metacritic_slug: str
    status: LetsPlayStatus | None
    video_url: str | None = None
    video_title: str | None = None
    view_count: int | None = None
    conclusion: str | None = None
    highlights: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class GameRecord:
    id: UUID
    metacritic_slug: str
    title: str
    listing_url: str | None
    cover_url: str | None
    cover_source_url: str | None
    developer: str | None
    publisher: str | None
    genres: tuple[str, ...]
    release_date: date | None
    description: str | None
    video_url: str | None
    critic_likes: tuple[str, ...] | None
    critic_dislikes: tuple[str, ...] | None
    critic_summary: str | None
    user_likes: tuple[str, ...] | None
    user_dislikes: tuple[str, ...] | None
    user_summary: str | None
    letsplay_status: LetsPlayStatus | None
    letsplay_video_url: str | None
    letsplay_video_title: str | None
    letsplay_view_count: int | None
    letsplay_conclusion: str | None
    letsplay_highlights: tuple[str, ...] | None
    embedding_input_hash: str | None
    created_at: datetime
    updated_at: datetime
    platforms: tuple[PlatformScoreRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class GameListItem:
    id: UUID
    metacritic_slug: str
    title: str
    cover_url: str | None
    developer: str | None
    max_metascore: int | None
    max_userscore: Decimal | None
    platforms: tuple[str, ...]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class GameListPage:
    items: tuple[GameListItem, ...]
    total: int
    page: int
    page_size: int
    sort: GameSort
    order: SortOrder


@dataclass(frozen=True, slots=True)
class SimilarNeighbor:
    similar_game_id: UUID
    score: float
    rank: int
    score_vector: float | None = None


@dataclass(frozen=True, slots=True)
class SimilarityGame:
    id: UUID
    metacritic_slug: str
    title: str
    developer: str | None
    publisher: str | None
    genres: tuple[str, ...]
    description: str | None
    critic_summary: str | None
    user_summary: str | None
    release_date: date | None
    platform_codes: tuple[str, ...]
    embedding: tuple[float, ...] | None
    embedding_input_hash: str | None


@dataclass(frozen=True, slots=True)
class SimilarGameRecord:
    metacritic_slug: str
    title: str
    score: float
    rank: int
    score_vector: float | None = None


@dataclass(frozen=True, slots=True)
class IngestionCursorRecord:
    process_date: date
    new_releases_done: bool
    last_browse_page: int | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class IngestionRunRecord:
    id: UUID
    process_date: date
    source: str
    page: int | None
    limit: int
    trigger: RunTrigger
    status: IngestionRunStatus
    discovered_count: int
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class IngestionItemRecord:
    id: UUID
    run_id: UUID
    game_id: UUID | None
    metacritic_slug: str
    process_date: date
    stage: IngestionStage
    status: IngestionItemStatus
    attempt_count: int
    error_type: str | None
    error_message: str | None
    event_id: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class HeartbeatRecord:
    worker_type: str
    instance_id: str
    status: str
    current_subject: str | None
    processed_ok: int
    processed_failed: int
    lag_hint: int | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class StageStatusCount:
    stage: str
    status: str
    count: int


@dataclass(frozen=True, slots=True)
class AdapterHealthRecord:
    adapter_name: str
    circuit_state: str
    parse_error_streak: int
    opened_at: datetime | None
    last_parse_error_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    id: int
    producer: str
    idempotency_key: str
    topic: str
    partition_key: str
    payload: dict[str, Any]
    created_at: datetime
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class OutboxInsert:
    producer: str
    idempotency_key: str
    topic: str
    partition_key: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InsertResult[IdT]:
    outcome: InsertOutcome
    id: IdT | None = None


@dataclass(frozen=True, slots=True)
class MonitorItemRecord:
    id: UUID
    run_id: UUID
    metacritic_slug: str
    title: str | None
    stage: IngestionStage
    status: IngestionItemStatus
    error_type: str | None
    error_message: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MonitorAggregates:
    heartbeats: tuple[HeartbeatRecord, ...]
    cursor: IngestionCursorRecord | None
    runs: tuple[IngestionRunRecord, ...]
    stage_counts: tuple[StageStatusCount, ...]
    adapter_health: tuple[AdapterHealthRecord, ...] = field(default_factory=tuple)
    parse_error_count: int = 0
    items: tuple[MonitorItemRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PageCacheRecord:
    url_hash: str
    fetched_at: datetime
    body: str
    content_type: str | None
    http_status: int
