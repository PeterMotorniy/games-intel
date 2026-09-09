from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from games_intel.contracts import (
    CloudEvent,
    DeadLetter,
    GameCataloged,
    GameLetsPlayAnalyzed,
    GameReviewsSummarized,
    GameSimilarAssigned,
    GamesPageListed,
    PlatformScore,
    ReviewSummary,
    RunRequested,
    ScheduleTick,
    SimilarGameRef,
    SimilarityRecomputeRequested,
    WorkerHeartbeat,
    build_cloud_event,
    uuid7,
)
from games_intel.contracts.generate import check_artifacts, render_artifacts, repo_root
from games_intel.contracts.registry import EVENT_KEY_TO_PAYLOAD
from games_intel.settings import Settings

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "events"
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-000000000001")
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
PROCESS_DATE = date(2026, 9, 7)


def _payloads() -> dict[str, Any]:
    empty_summary = ReviewSummary(likes=[], dislikes=[], summary="")
    return {
        "ScheduleTick": ScheduleTick(
            trigger="cron",
            requested_at=NOW,
            process_date=PROCESS_DATE,
        ),
        "RunRequested": RunRequested(
            run_id=RUN_ID,
            process_date=PROCESS_DATE,
            source="new_releases",
            page=None,
            limit=20,
            trigger="cron",
        ),
        "GamesPageListed": GamesPageListed.model_validate(
            {
                "run_id": RUN_ID,
                "process_date": PROCESS_DATE,
                "source": "new_releases",
                "page": None,
                "games": [
                    {
                        "metacritic_slug": "elden-ring",
                        "title": "Elden Ring",
                        "listing_url": "https://www.metacritic.com/game/elden-ring/",
                        "position": 0,
                    }
                ],
            }
        ),
        "GameCataloged": GameCataloged.model_validate(
            {
                "run_id": RUN_ID,
                "process_date": PROCESS_DATE,
                "metacritic_slug": "elden-ring",
                "title": "Elden Ring",
                "cover_url": "/api/v1/media/covers/elden-ring",
                "cover_source_url": "https://static.metacritic.com/elden-ring.jpg",
                "developer": "FromSoftware",
                "publisher": "Bandai Namco",
                "genres": ["action", "rpg"],
                "release_date": date(2022, 2, 25),
                "description": "Open-world action RPG.",
                "video_url": "https://www.youtube.com/watch?v=example",
                "platforms": [
                    PlatformScore(platform_code="ps5", metascore=96, userscore=7.8),
                    PlatformScore(platform_code="pc", metascore=94, userscore=None),
                ],
            }
        ),
        "GameReviewsSummarized": GameReviewsSummarized(
            run_id=RUN_ID,
            metacritic_slug="elden-ring",
            critic=ReviewSummary(
                likes=["combat"],
                dislikes=["performance"],
                summary="Critics praise combat.",
            ),
            user=empty_summary,
            critic_review_count=12,
            user_review_count=0,
            degraded=False,
        ),
        "GameLetsPlayAnalyzed": GameLetsPlayAnalyzed.model_validate(
            {
                "run_id": RUN_ID,
                "metacritic_slug": "elden-ring",
                "status": "ok",
                "video_url": "https://www.youtube.com/watch?v=letsplay",
                "video_title": "Elden Ring Let's Play",
                "view_count": 1_000_000,
                "conclusion": "Блогер в восторге от мира.",
                "highlights": ["исследование", "боссы"],
            }
        ),
        "GameSimilarAssigned": GameSimilarAssigned(
            run_id=RUN_ID,
            metacritic_slug="elden-ring",
            items=[
                SimilarGameRef(
                    metacritic_slug="dark-souls-3",
                    title="Dark Souls III",
                    score=0.91,
                    rank=1,
                )
            ],
        ),
        "SimilarityRecomputeRequested": SimilarityRecomputeRequested(
            run_id=RUN_ID,
            process_date=PROCESS_DATE,
            scope="all",
            center_slug=None,
            candidate_slugs=[],
            reason="schedule",
        ),
        "WorkerHeartbeat": WorkerHeartbeat(
            worker_type="catalog",
            instance_id="catalog-1",
            status="idle",
            current_subject=None,
            processed_ok=3,
            processed_failed=0,
            lag_hint=0,
            observed_at=NOW,
        ),
        "DeadLetter": DeadLetter(
            original_topic="games.page.listed",
            original_id="evt-1",
            reason="schema",
            error_type="ValidationError",
            error_message="missing field",
            payload_truncated=False,
        ),
    }


def test_golden_json_for_each_payload() -> None:
    payloads = _payloads()
    assert set(payloads) == {cls.__name__ for cls in EVENT_KEY_TO_PAYLOAD.values()}
    for name, model in payloads.items():
        golden_path = FIXTURES / f"{name}.json"
        dumped = model.model_dump(mode="json")
        expected = json.loads(golden_path.read_text(encoding="utf-8"))
        assert dumped == expected


def _envelope(**overrides: Any) -> dict[str, Any]:
    payload = {
        "specversion": "1.0",
        "id": "evt-1",
        "source": "urn:games-intel:worker:catalog",
        "type": "game.cataloged",
        "time": "2026-09-07T12:00:00Z",
        "datacontenttype": "application/json",
        "dataschema": "https://games-intel.local/schemas/GameCataloged.json",
        "subject": "elden-ring",
        "idempotencykey": "game.cataloged:run:elden-ring:cataloged",
        "data": {"ok": True},
        "runid": str(RUN_ID),
        "traceparent": None,
    }
    payload.update(overrides)
    return payload


def test_idempotencykey_required() -> None:
    payload = _envelope()
    del payload["idempotencykey"]
    with pytest.raises(ValidationError):
        CloudEvent[dict[str, Any]].model_validate(payload)


def test_invalid_specversion_rejected() -> None:
    with pytest.raises(ValidationError):
        CloudEvent[dict[str, Any]].model_validate(_envelope(specversion="0.3"))


def test_two_envelopes_same_business_key_different_ids() -> None:
    first = CloudEvent[dict[str, Any]].model_validate(_envelope(id="id-a"))
    second = CloudEvent[dict[str, Any]].model_validate(_envelope(id="id-b"))
    assert first.id != second.id
    assert first.idempotencykey == second.idempotencykey


def test_metascore_tbd_becomes_null() -> None:
    score = PlatformScore.model_validate(
        {"platform_code": "ps5", "metascore": "tbd", "userscore": None}
    )
    assert score.metascore is None
    dumped = score.model_dump()
    assert dumped["metascore"] is None
    assert dumped["metascore"] != 0


def test_builder_reads_type_from_settings() -> None:
    settings = Settings()
    event = build_cloud_event(
        settings,
        "page_listed",
        source="urn:games-intel:worker:discovery",
        subject=str(RUN_ID),
        data=_payloads()["GamesPageListed"],
        stage="discovered",
        run_id=RUN_ID,
        event_id="custom-id",
        occurred_at=NOW,
    )
    assert event.type == settings.event_name("page_listed")
    assert event.idempotencykey == (f"{event.type}:{RUN_ID}:{RUN_ID}:discovered")


def test_builder_default_id_is_uuid7() -> None:
    event = build_cloud_event(
        Settings(),
        "page_listed",
        source="urn:games-intel:worker:discovery",
        subject=str(RUN_ID),
        data=_payloads()["GamesPageListed"],
        stage="discovered",
        run_id=RUN_ID,
        occurred_at=NOW,
    )
    assert UUID(event.id).version == 7
    assert uuid7().version == 7


def test_schema_generation_does_not_drift() -> None:
    assert render_artifacts()
    assert check_artifacts(repo_root()) == []
