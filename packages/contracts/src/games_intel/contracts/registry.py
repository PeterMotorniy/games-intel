from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from games_intel.contracts.payloads import (
    DeadLetter,
    GameCataloged,
    GameLetsPlayAnalyzed,
    GameListed,
    GameReviewsSummarized,
    GameSimilarAssigned,
    GamesPageListed,
    RunRequested,
    ScheduleTick,
    SimilarityRecomputeRequested,
    WorkerHeartbeat,
)

EVENT_KEY_TO_PAYLOAD: Mapping[str, type[BaseModel]] = {
    "schedule_tick": ScheduleTick,
    "run_requested": RunRequested,
    "page_listed": GamesPageListed,
    "game_listed": GameListed,
    "game_cataloged": GameCataloged,
    "game_reviews_summarized": GameReviewsSummarized,
    "game_letsplay_analyzed": GameLetsPlayAnalyzed,
    "game_similar_assigned": GameSimilarAssigned,
    "similarity_recompute": SimilarityRecomputeRequested,
    "worker_heartbeat": WorkerHeartbeat,
    "dlq": DeadLetter,
}


def payload_model_for_event_key(event_key: str) -> type[BaseModel]:
    try:
        return EVENT_KEY_TO_PAYLOAD[event_key]
    except KeyError as exc:
        msg = f"unknown event key: {event_key}"
        raise KeyError(msg) from exc
