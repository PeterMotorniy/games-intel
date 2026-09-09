from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from games_intel.api.schemas import (
    CircuitStateName,
    CollectionStateRead,
    GameCardRead,
    GameHydrationRead,
    GameListItemRead,
    GameListResponse,
    IngestionItemStatusName,
    IngestionStageName,
    LetsPlayRead,
    MonitorCursorRead,
    MonitorItemRead,
    MonitorRunRead,
    MonitorScrapeRead,
    MonitorSnapshot,
    PaginationMeta,
    StageStatusCountRead,
    WorkerHeartbeatRead,
    WorkerStatusName,
)
from games_intel.contracts.payloads import (
    LetsPlayStatus,
    PlatformScore,
    ReviewSummary,
    SimilarGameRef,
)
from games_intel.db.records import (
    GameListItem,
    GameListPage,
    GameRecord,
    IngestionItemRecord,
    MonitorAggregates,
    MonitorItemRecord,
    SimilarGameRecord,
)
from games_intel.db.types import GameSort, IngestionItemStatus, IngestionStage, SortOrder
from games_intel.kafka.logging import sanitize_error_message


def _userscore(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _item_for(
    items: dict[tuple[str, IngestionStage], IngestionItemRecord],
    slug: str,
    stage: IngestionStage,
) -> IngestionItemRecord | None:
    return items.get((slug, stage))


def collection_state(
    *,
    has_content: bool,
    item: IngestionItemRecord | None,
    domain_empty: bool = False,
    domain_error: bool = False,
) -> CollectionStateRead:
    if has_content:
        return CollectionStateRead(status="ready")
    if domain_error:
        return CollectionStateRead(
            status="error",
            error_type=None if item is None else item.error_type,
            error_message=_public_error_message(None if item is None else item.error_message),
        )
    if domain_empty:
        return CollectionStateRead(status="empty")
    if item is None or item.status is IngestionItemStatus.pending:
        return CollectionStateRead(status="idle")
    if item.status is IngestionItemStatus.running:
        return CollectionStateRead(status="loading")
    if item.status is IngestionItemStatus.failed:
        return CollectionStateRead(
            status="error",
            error_type=item.error_type,
            error_message=_public_error_message(item.error_message),
        )
    return CollectionStateRead(status="empty")


def _catalog_has_content(game: GameRecord | GameListItem) -> bool:
    if isinstance(game, GameListItem):
        return bool(
            game.cover_url
            or (game.developer and game.developer.strip())
            or game.max_metascore is not None
            or game.max_userscore is not None
            or game.platforms
        )
    return bool(
        game.cover_url
        or (game.developer and game.developer.strip())
        or (game.publisher and game.publisher.strip())
        or game.description
        or game.video_url
        or game.genres
        or game.release_date
        or game.platforms
    )


def _review_has_copy(summary: ReviewSummary | None) -> bool:
    if summary is None:
        return False
    return bool(summary.summary.strip() or summary.likes or summary.dislikes)


def _letsplay_has_content(game: GameRecord) -> bool:
    if game.letsplay_conclusion and game.letsplay_conclusion.strip():
        return True
    return (
        game.letsplay_status is not None
        and game.letsplay_status.value == "ok"
        and bool(game.letsplay_video_url)
    )


def game_hydration(
    game: GameRecord,
    similar: tuple[SimilarGameRecord, ...],
    items: dict[tuple[str, IngestionStage], IngestionItemRecord],
) -> GameHydrationRead:
    slug = game.metacritic_slug
    critic = _review(game.critic_likes, game.critic_dislikes, game.critic_summary)
    user = _review(game.user_likes, game.user_dislikes, game.user_summary)
    letsplay_status = None if game.letsplay_status is None else game.letsplay_status.value
    return GameHydrationRead(
        catalog=collection_state(
            has_content=_catalog_has_content(game),
            item=_item_for(items, slug, IngestionStage.cataloged),
        ),
        critic=collection_state(
            has_content=_review_has_copy(critic),
            item=_item_for(items, slug, IngestionStage.reviews),
        ),
        user=collection_state(
            has_content=_review_has_copy(user),
            item=_item_for(items, slug, IngestionStage.reviews),
        ),
        letsplay=collection_state(
            has_content=_letsplay_has_content(game),
            item=_item_for(items, slug, IngestionStage.letsplay),
            domain_empty=letsplay_status in {"no_video", "transcript_unavailable"},
            domain_error=letsplay_status == "quota_exceeded",
        ),
        similar=collection_state(
            has_content=any(row.metacritic_slug != slug for row in similar),
            item=_item_for(items, slug, IngestionStage.similar),
        ),
    )


def game_list_item(
    item: GameListItem,
    items: dict[tuple[str, IngestionStage], IngestionItemRecord] | None = None,
) -> GameListItemRead:
    stage_items = items or {}
    return GameListItemRead(
        metacritic_slug=item.metacritic_slug,
        title=item.title,
        cover_url=item.cover_url,
        developer=item.developer,
        metascore=item.max_metascore,
        userscore=_userscore(item.max_userscore),
        platforms=list(item.platforms),
        updated_at=item.updated_at,
        catalog_collection=collection_state(
            has_content=_catalog_has_content(item),
            item=_item_for(stage_items, item.metacritic_slug, IngestionStage.cataloged),
        ),
    )


def game_list_response(
    page: GameListPage,
    items: dict[tuple[str, IngestionStage], IngestionItemRecord] | None = None,
) -> GameListResponse:
    stage_items = items or {}
    return GameListResponse(
        items=[game_list_item(item, stage_items) for item in page.items],
        meta=PaginationMeta(
            page=page.page,
            page_size=page.page_size,
            total=page.total,
            sort=page.sort.value,
            order=page.order.value,
        ),
    )


def _review(
    likes: tuple[str, ...] | None,
    dislikes: tuple[str, ...] | None,
    summary: str | None,
) -> ReviewSummary | None:
    if likes is None and dislikes is None and summary is None:
        return None
    return ReviewSummary(
        likes=list(likes or ()),
        dislikes=list(dislikes or ()),
        summary=summary or "",
    )


def _letsplay_status(value: str | None) -> LetsPlayStatus | None:
    if value == "ok":
        return "ok"
    if value == "no_video":
        return "no_video"
    if value == "transcript_unavailable":
        return "transcript_unavailable"
    if value == "quota_exceeded":
        return "quota_exceeded"
    return None


def _letsplay(game: GameRecord) -> LetsPlayRead | None:
    if (
        game.letsplay_status is None
        and game.letsplay_video_url is None
        and game.letsplay_video_title is None
        and game.letsplay_view_count is None
        and game.letsplay_conclusion is None
        and game.letsplay_highlights is None
    ):
        return None
    highlights = list(game.letsplay_highlights) if game.letsplay_highlights is not None else None
    status = _letsplay_status(None if game.letsplay_status is None else game.letsplay_status.value)
    return LetsPlayRead(
        status=status,
        video_url=game.letsplay_video_url,
        video_title=game.letsplay_video_title,
        view_count=game.letsplay_view_count,
        conclusion=game.letsplay_conclusion,
        highlights=highlights,
    )


def similar_items(
    slug: str,
    rows: tuple[SimilarGameRecord, ...],
) -> list[SimilarGameRef]:
    return [
        SimilarGameRef(
            metacritic_slug=row.metacritic_slug,
            title=row.title,
            score=row.score,
            rank=row.rank,
        )
        for row in rows
        if row.metacritic_slug != slug
    ]


def game_card(
    game: GameRecord,
    similar: tuple[SimilarGameRecord, ...],
    items: dict[tuple[str, IngestionStage], IngestionItemRecord] | None = None,
) -> GameCardRead:
    stage_items = items or {}
    return GameCardRead(
        metacritic_slug=game.metacritic_slug,
        title=game.title,
        cover_url=game.cover_url,
        developer=game.developer,
        publisher=game.publisher,
        description=game.description,
        video_url=game.video_url,
        genres=list(game.genres),
        release_date=game.release_date,
        platforms=[
            PlatformScore(
                platform_code=row.platform_code,
                metascore=row.metascore,
                userscore=_userscore(row.userscore),
            )
            for row in game.platforms
        ],
        critic=_review(game.critic_likes, game.critic_dislikes, game.critic_summary),
        user=_review(game.user_likes, game.user_dislikes, game.user_summary),
        letsplay=_letsplay(game),
        similar=similar_items(game.metacritic_slug, similar),
        hydration=game_hydration(game, similar, stage_items),
    )


def parse_sort(value: str) -> GameSort:
    return GameSort(value)


def parse_order(value: str) -> SortOrder:
    return SortOrder(value)


_CIRCUIT_STATES: dict[str, CircuitStateName] = {
    "closed": "closed",
    "open": "open",
    "half_open": "half_open",
}
_WORKER_STATUSES: dict[str, WorkerStatusName] = {
    "idle": "idle",
    "running": "running",
    "error": "error",
}
_ITEM_STATUSES: dict[str, IngestionItemStatusName] = {
    "pending": "pending",
    "running": "running",
    "completed": "completed",
    "failed": "failed",
    "degraded": "degraded",
}
_ITEM_STAGES: dict[str, IngestionStageName] = {
    "discovered": "discovered",
    "cataloged": "cataloged",
    "reviews": "reviews",
    "letsplay": "letsplay",
    "similar": "similar",
}
_PROMPT_OR_TRANSCRIPT_RE = re.compile(r"(?i)(?:prompt|transcript)\s*[:=]\s*\S+")


def _circuit_state(value: str | None) -> CircuitStateName | None:
    if value is None:
        return None
    return _CIRCUIT_STATES.get(value)


def _worker_status(value: str) -> WorkerStatusName:
    return _WORKER_STATUSES.get(value, "error")


def _item_status(value: str) -> IngestionItemStatusName:
    return _ITEM_STATUSES.get(value, "failed")


def _item_stage(value: str) -> IngestionStageName:
    return _ITEM_STAGES[value]


def _public_error_message(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = sanitize_error_message(value)
    cleaned = _PROMPT_OR_TRANSCRIPT_RE.sub("[redacted]", cleaned)
    return cleaned


def _monitor_item(row: MonitorItemRecord) -> MonitorItemRead:
    return MonitorItemRead(
        id=row.id,
        run_id=row.run_id,
        metacritic_slug=row.metacritic_slug,
        title=row.title,
        stage=_item_stage(row.stage.value),
        status=_item_status(row.status.value),
        error_type=row.error_type,
        error_message=_public_error_message(row.error_message),
        updated_at=row.updated_at,
    )


def monitor_snapshot(
    aggregates: MonitorAggregates,
    *,
    process_date: date,
    stale_after_seconds: int,
    now: datetime,
    include_circuit: bool,
    include_last_parse_error: bool,
    show_instance_id: bool,
) -> MonitorSnapshot:
    workers = [
        WorkerHeartbeatRead(
            worker_type=row.worker_type,
            instance_id=row.instance_id if show_instance_id else "",
            status=_worker_status(row.status),
            current_subject=row.current_subject,
            processed_ok=row.processed_ok,
            processed_failed=row.processed_failed,
            lag_hint=row.lag_hint,
            observed_at=row.observed_at,
            stale=(now - row.observed_at).total_seconds() > stale_after_seconds,
        )
        for row in aggregates.heartbeats
    ]
    runs = [
        MonitorRunRead(
            id=row.id,
            process_date=row.process_date,
            source=row.source,
            page=row.page,
            limit=row.limit,
            trigger=row.trigger.value,
            status=row.status.value,
            discovered_count=row.discovered_count,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
        for row in aggregates.runs
    ]
    counts = [
        StageStatusCountRead(stage=row.stage, status=row.status, count=row.count)
        for row in aggregates.stage_counts
    ]
    items = [_monitor_item(row) for row in aggregates.items]
    cursor = None
    if aggregates.cursor is not None:
        cursor = MonitorCursorRead(
            process_date=aggregates.cursor.process_date,
            new_releases_done=aggregates.cursor.new_releases_done,
            last_browse_page=aggregates.cursor.last_browse_page,
        )
    health = next(
        (row for row in aggregates.adapter_health if row.adapter_name == "metacritic"),
        None,
    )
    scrape = MonitorScrapeRead(
        circuit_state=_circuit_state(health.circuit_state) if include_circuit and health else None,
        last_parse_error_at=(
            health.last_parse_error_at if include_last_parse_error and health else None
        ),
        parse_error_count=aggregates.parse_error_count,
    )
    return MonitorSnapshot(
        process_date=process_date,
        workers=workers,
        runs=runs,
        items=items,
        counts=counts,
        cursor=cursor,
        scrape=scrape,
    )
