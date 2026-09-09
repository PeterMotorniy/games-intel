from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any

from games_intel.db.models import (
    AdapterHealth,
    ExternalPageCache,
    Game,
    GamePlatform,
    IngestionCursor,
    IngestionItem,
    IngestionRun,
    Outbox,
    SimilarGame,
    WorkerHeartbeat,
)
from games_intel.db.records import (
    AdapterHealthRecord,
    GameListItem,
    GameRecord,
    HeartbeatRecord,
    IngestionCursorRecord,
    IngestionItemRecord,
    IngestionRunRecord,
    OutboxRecord,
    PageCacheRecord,
    PlatformScoreRecord,
    SimilarGameRecord,
    SimilarityGame,
)
from games_intel.db.types import (
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionStage,
    LetsPlayStatus,
    RunTrigger,
)


def _json_strings(value: list[str] | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    return tuple(value)


def _required_strings(value: list[str] | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(value)


def letsplay_status_from_db(value: str | None) -> LetsPlayStatus | None:
    if value is None:
        return None
    return LetsPlayStatus(value)


def platform_record(row: GamePlatform) -> PlatformScoreRecord:
    userscore = row.userscore
    return PlatformScoreRecord(
        platform_code=row.platform_code,
        metascore=row.metascore,
        userscore=Decimal(userscore) if userscore is not None else None,
    )


def game_record(game: Game, platforms: list[GamePlatform] | None = None) -> GameRecord:
    platform_rows = platforms if platforms is not None else list(game.platforms)
    return GameRecord(
        id=game.id,
        metacritic_slug=game.metacritic_slug,
        title=game.title,
        listing_url=game.listing_url,
        cover_url=game.cover_url,
        cover_source_url=game.cover_source_url,
        developer=game.developer,
        publisher=game.publisher,
        genres=_required_strings(game.genres),
        release_date=game.release_date,
        description=game.description,
        video_url=game.video_url,
        critic_likes=_json_strings(game.critic_likes),
        critic_dislikes=_json_strings(game.critic_dislikes),
        critic_summary=game.critic_summary,
        user_likes=_json_strings(game.user_likes),
        user_dislikes=_json_strings(game.user_dislikes),
        user_summary=game.user_summary,
        letsplay_status=letsplay_status_from_db(game.letsplay_status),
        letsplay_video_url=game.letsplay_video_url,
        letsplay_video_title=game.letsplay_video_title,
        letsplay_view_count=game.letsplay_view_count,
        letsplay_conclusion=game.letsplay_conclusion,
        letsplay_highlights=_json_strings(game.letsplay_highlights),
        embedding_input_hash=game.embedding_input_hash,
        created_at=game.created_at,
        updated_at=game.updated_at,
        platforms=tuple(platform_record(row) for row in platform_rows),
    )


def game_list_item(
    game: Game,
    *,
    max_metascore: int | None,
    max_userscore: Decimal | None,
    platform_codes: tuple[str, ...],
) -> GameListItem:
    return GameListItem(
        id=game.id,
        metacritic_slug=game.metacritic_slug,
        title=game.title,
        cover_url=game.cover_url,
        developer=game.developer,
        max_metascore=max_metascore,
        max_userscore=max_userscore,
        platforms=platform_codes,
        updated_at=game.updated_at,
    )


def cursor_record(row: IngestionCursor) -> IngestionCursorRecord:
    return IngestionCursorRecord(
        process_date=row.process_date,
        new_releases_done=row.new_releases_done,
        last_browse_page=row.last_browse_page,
        updated_at=row.updated_at,
    )


def run_record(row: IngestionRun) -> IngestionRunRecord:
    return IngestionRunRecord(
        id=row.id,
        process_date=row.process_date,
        source=row.source,
        page=row.page,
        limit=row.limit,
        trigger=RunTrigger(row.trigger),
        status=IngestionRunStatus(row.status),
        discovered_count=row.discovered_count,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def item_record(row: IngestionItem) -> IngestionItemRecord:
    return IngestionItemRecord(
        id=row.id,
        run_id=row.run_id,
        game_id=row.game_id,
        metacritic_slug=row.metacritic_slug,
        process_date=row.process_date,
        stage=IngestionStage(row.stage),
        status=IngestionItemStatus(row.status),
        attempt_count=row.attempt_count,
        error_type=row.error_type,
        error_message=row.error_message,
        event_id=row.event_id,
        updated_at=row.updated_at,
    )


def heartbeat_record(row: WorkerHeartbeat) -> HeartbeatRecord:
    return HeartbeatRecord(
        worker_type=row.worker_type,
        instance_id=row.instance_id,
        status=row.status,
        current_subject=row.current_subject,
        processed_ok=row.processed_ok,
        processed_failed=row.processed_failed,
        lag_hint=row.lag_hint,
        observed_at=row.observed_at,
    )


def adapter_health_record(row: AdapterHealth) -> AdapterHealthRecord:
    return AdapterHealthRecord(
        adapter_name=row.adapter_name,
        circuit_state=row.circuit_state,
        parse_error_streak=row.parse_error_streak,
        opened_at=row.opened_at,
        last_parse_error_at=row.last_parse_error_at,
        updated_at=row.updated_at,
    )


def page_cache_record(row: ExternalPageCache) -> PageCacheRecord:
    return PageCacheRecord(
        url_hash=row.url_hash,
        fetched_at=row.fetched_at,
        body=row.body,
        content_type=row.content_type,
        http_status=row.http_status,
    )


def outbox_record(row: Outbox) -> OutboxRecord:
    payload: dict[str, Any] = dict(row.payload)
    return OutboxRecord(
        id=row.id,
        producer=row.producer,
        idempotency_key=row.idempotency_key,
        topic=row.topic,
        partition_key=row.partition_key,
        payload=payload,
        created_at=row.created_at,
        published_at=row.published_at,
    )


def similar_record(
    slug: str,
    title: str,
    row: SimilarGame,
) -> SimilarGameRecord:
    return SimilarGameRecord(
        metacritic_slug=slug,
        title=title,
        score=row.score,
        rank=row.rank,
        score_vector=row.score_vector,
    )


def _embedding_tuple(value: object) -> tuple[float, ...] | None:
    if value is None:
        return None
    if isinstance(value, str | bytes) or not isinstance(value, Iterable):
        msg = "embedding must be a sequence of floats"
        raise TypeError(msg)
    return tuple(float(item) for item in value)


def similarity_game(game: Game, platform_codes: tuple[str, ...] | None = None) -> SimilarityGame:
    codes = (
        platform_codes
        if platform_codes is not None
        else tuple(row.platform_code for row in game.platforms)
    )
    return SimilarityGame(
        id=game.id,
        metacritic_slug=game.metacritic_slug,
        title=game.title,
        developer=game.developer,
        publisher=game.publisher,
        genres=_required_strings(game.genres),
        description=game.description,
        critic_summary=game.critic_summary,
        user_summary=game.user_summary,
        release_date=game.release_date,
        platform_codes=codes,
        embedding=_embedding_tuple(game.embedding),
        embedding_input_hash=game.embedding_input_hash,
    )


def utcnow() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
