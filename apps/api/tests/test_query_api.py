from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.adapters.media.storage import FilesystemCoverStorage
from games_intel.api.app import ReadyFn, create_app
from games_intel.db.records import CatalogSlice, PlatformScoreRecord, ReviewsSlice, SimilarNeighbor
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.reviews import GameReviewsRepository
from games_intel.db.repositories.similar import SimilarGamesRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage, RunTrigger
from games_intel.settings import Settings
from games_intel.settings.config import MediaSettings

JPEG = b"\xff\xd8\xff" + b"\x00" * 16
PROBLEM_JSON = "application/problem+json"


def _settings(tmp_path: Path) -> Settings:
    base = Settings()
    media = MediaSettings(
        covers_dir=str(tmp_path),
        covers_url_prefix=base.media.covers_url_prefix,
        covers_cache_control=base.media.covers_cache_control,
    )
    return base.model_copy(update={"media": media})


def _catalog(
    slug: str,
    title: str,
    *,
    platforms: tuple[PlatformScoreRecord, ...] = (),
    developer: str | None = "FromSoftware",
) -> CatalogSlice:
    return CatalogSlice(
        metacritic_slug=slug,
        title=title,
        listing_url=f"https://www.metacritic.com/game/{slug}/",
        cover_url=f"/api/v1/media/covers/{slug}",
        developer=developer,
        publisher="Bandai",
        genres=("Action", "RPG"),
        release_date=date(2022, 2, 25),
        description="An open-world action RPG.",
        video_url="https://www.youtube.com/watch?v=abc",
        platforms=platforms
        or (PlatformScoreRecord(platform_code="ps5", metascore=96, userscore=Decimal("7.8")),),
    )


async def _never_ready() -> bool:
    return False


async def _always_ready() -> bool:
    return True


def _app(
    settings: Settings,
    *,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    covers: FilesystemCoverStorage | None = None,
    postgres_ready: ReadyFn | None = None,
    kafka_ready: ReadyFn | None = None,
) -> FastAPI:
    return create_app(
        settings,
        engine=engine,
        session_factory=session_factory,
        covers=covers,
        postgres_ready=postgres_ready if postgres_ready is not None else _never_ready,
        kafka_ready=kafka_ready if kafka_ready is not None else _never_ready,
    )


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def api_client(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> AsyncIterator[httpx.AsyncClient]:
    settings = _settings(tmp_path)
    covers = FilesystemCoverStorage(settings.media)
    app = _app(
        settings,
        engine=engine,
        session_factory=session_factory,
        covers=covers,
        postgres_ready=_always_ready,
    )
    async for client in _client(app):
        yield client


def test_openapi_contains_games_paths_and_read_schemas() -> None:
    schema = create_app(Settings(), postgres_ready=_never_ready, kafka_ready=_never_ready).openapi()
    paths = schema["paths"]
    assert "/api/v1/games" in paths
    assert "/api/v1/games/{slug}" in paths
    assert "/api/v1/platforms" in paths
    assert "/api/v1/media/covers/{slug}" in paths
    assert "/healthz" in paths
    assert "/readyz" in paths
    assert "/api/v1/monitor" in paths
    assert "/api/v1/runs" in paths
    models = schema["components"]["schemas"]
    assert "GameCardRead" in models
    assert "GameListResponse" in models
    assert "ProblemDetails" in models
    card = models["GameCardRead"]["properties"]
    assert "letsplay" in card
    assert "hydration" in card
    assert "metascore" in card
    assert "userscore" in card
    assert "catalog_collection" in models["GameListItemRead"]["properties"]
    assert "critic" in card
    similar_ref = models["SimilarGameRef"]["properties"]["score"]
    assert similar_ref.get("type") == "number" or "number" in str(similar_ref)
    letsplay = models["GameCardRead"]["properties"]["letsplay"]
    assert "anyOf" in letsplay or letsplay.get("nullable") is True


async def test_healthz_does_not_need_database() -> None:
    app = create_app(Settings(), postgres_ready=_never_ready, kafka_ready=_never_ready)
    async for client in _client(app):
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


async def test_readyz_503_without_postgres() -> None:
    app = create_app(Settings(), postgres_ready=_never_ready, kafka_ready=_never_ready)
    async for client in _client(app):
        response = await client.get("/readyz")
        assert response.status_code == 503
        assert response.headers["content-type"].startswith(PROBLEM_JSON)
        body = response.json()
        assert body["status"] == 503
        assert body["title"] == "Service Unavailable"
        assert body["postgres"] is False


async def test_readyz_ok_with_postgres(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    app = _app(
        _settings(tmp_path),
        engine=engine,
        session_factory=session_factory,
        postgres_ready=_always_ready,
        kafka_ready=_never_ready,
    )
    async for client in _client(app):
        response = await client.get("/readyz")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["postgres"] is True
        assert body["kafka"] is False


async def test_list_search_platform_sort_pagination(
    api_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    catalog = GameCatalogRepository(session)
    await catalog.upsert_catalog(
        _catalog(
            "low-score",
            "Zebra Quest",
            platforms=(
                PlatformScoreRecord(platform_code="ns2", metascore=70, userscore=Decimal("8.1")),
            ),
        )
    )
    await catalog.upsert_catalog(
        _catalog(
            "high-score",
            "Alpha Strike",
            platforms=(
                PlatformScoreRecord(platform_code="ps5", metascore=95, userscore=Decimal("5.0")),
            ),
        )
    )
    await catalog.upsert_catalog(
        _catalog(
            "unscored",
            "Null Realm",
            platforms=(PlatformScoreRecord(platform_code="pc", metascore=None, userscore=None),),
        )
    )
    await session.commit()

    by_score = await api_client.get("/api/v1/games", params={"sort": "metascore", "order": "desc"})
    assert by_score.status_code == 200
    slugs = [item["metacritic_slug"] for item in by_score.json()["items"]]
    assert slugs == ["high-score", "low-score", "unscored"]

    search = await api_client.get("/api/v1/games", params={"q": "zebra"})
    assert [item["metacritic_slug"] for item in search.json()["items"]] == ["low-score"]

    filtered = await api_client.get("/api/v1/games", params={"platform": "ps5"})
    assert [item["metacritic_slug"] for item in filtered.json()["items"]] == ["high-score"]

    listed = await api_client.get("/api/v1/games", params={"sort": "title", "order": "asc"})
    assert [item["title"] for item in listed.json()["items"]] == [
        "Alpha Strike",
        "Null Realm",
        "Zebra Quest",
    ]
    page_two = await api_client.get(
        "/api/v1/games",
        params={"sort": "title", "order": "asc", "page": 2, "page_size": 1},
    )
    assert page_two.json()["meta"]["page"] == 2
    assert page_two.json()["meta"]["page_size"] == 1
    assert page_two.json()["meta"]["total"] == 3
    assert page_two.json()["items"][0]["title"] == "Null Realm"

    platforms = await api_client.get("/api/v1/platforms")
    assert platforms.json()["items"] == ["ns2", "pc", "ps5"]


async def test_page_size_over_max_is_problem_json(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/games", params={"page_size": 101})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    body = response.json()
    assert body["status"] == 400
    assert "page_size" in body["detail"]


async def test_game_card_404_and_partial_hydration(
    api_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    missing = await api_client.get("/api/v1/games/missing-slug")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith(PROBLEM_JSON)

    catalog = GameCatalogRepository(session)
    await catalog.upsert_catalog(_catalog("partial-game", "Partial"))
    await session.commit()
    response = await api_client.get("/api/v1/games/partial-game")
    assert response.status_code == 200
    body = response.json()
    assert body["critic"] is None
    assert body["user"] is None
    assert body["letsplay"] is None
    assert body["similar"] == []
    assert body["title"] == "Partial"
    assert body["metascore"] == 96
    assert body["userscore"] == 7.8
    assert body["hydration"]["catalog"]["status"] == "ready"
    assert body["hydration"]["critic"]["status"] == "idle"
    assert body["hydration"]["user"]["status"] == "idle"
    assert body["hydration"]["letsplay"]["status"] == "idle"
    assert body["hydration"]["similar"]["status"] == "idle"


async def test_game_card_collection_states_follow_ingestion_items(
    api_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    catalog = GameCatalogRepository(session)
    ingestion = IngestionRepository(session)
    await catalog.upsert_catalog(
        CatalogSlice(
            metacritic_slug="bare-game",
            title="Bare Game",
            listing_url="https://www.metacritic.com/game/bare-game/",
        )
    )
    run = await ingestion.create_run(
        process_date=date(2026, 9, 8),
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.manual,
    )
    assert run.id is not None
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="bare-game",
        process_date=date(2026, 9, 8),
        stage=IngestionStage.cataloged,
        status=IngestionItemStatus.running,
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="bare-game",
        process_date=date(2026, 9, 8),
        stage=IngestionStage.reviews,
        status=IngestionItemStatus.completed,
    )
    await ingestion.upsert_item(
        run_id=run.id,
        metacritic_slug="bare-game",
        process_date=date(2026, 9, 8),
        stage=IngestionStage.letsplay,
        status=IngestionItemStatus.failed,
        error_type="TimeoutError",
        error_message="sidecar request timed out",
    )
    await session.commit()

    response = await api_client.get("/api/v1/games/bare-game")
    assert response.status_code == 200
    body = response.json()
    assert body["hydration"]["catalog"]["status"] == "loading"
    assert body["hydration"]["critic"]["status"] == "empty"
    assert body["hydration"]["user"]["status"] == "empty"
    assert body["hydration"]["letsplay"]["status"] == "error"
    assert body["hydration"]["letsplay"]["error_type"] == "TimeoutError"
    listed = await api_client.get("/api/v1/games")
    assert listed.json()["items"][0]["catalog_collection"]["status"] == "loading"


async def test_game_card_similar_excludes_self(
    api_client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    catalog = GameCatalogRepository(session)
    similar = SimilarGamesRepository(session)
    reviews = GameReviewsRepository(session)
    id_a = await catalog.upsert_catalog(_catalog("elden-ring", "Elden Ring"))
    id_b = await catalog.upsert_catalog(_catalog("sekiro", "Sekiro"))
    await similar.replace_for_game(
        id_a,
        [SimilarNeighbor(similar_game_id=id_b, score=0.87, rank=1, score_vector=0.8)],
    )
    await reviews.update_reviews(
        ReviewsSlice(
            metacritic_slug="elden-ring",
            critic_likes=("combat",),
            critic_dislikes=("performance",),
            critic_summary="Great combat.",
            user_likes=("exploration",),
            user_dislikes=("difficulty",),
            user_summary="Harsh but fair.",
        )
    )
    await session.commit()

    response = await api_client.get("/api/v1/games/elden-ring")
    assert response.status_code == 200
    body = response.json()
    assert [item["metacritic_slug"] for item in body["similar"]] == ["sekiro"]
    assert "elden-ring" not in [item["metacritic_slug"] for item in body["similar"]]
    assert body["similar"][0]["score"] == pytest.approx(0.87)
    assert isinstance(body["similar"][0]["score"], float)
    assert body["critic"]["summary"] == "Great combat."
    assert body["platforms"][0]["platform_code"] == "ps5"


async def test_cover_404_and_cache_control(
    api_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    missing = await api_client.get("/api/v1/media/covers/no-such-cover")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith(PROBLEM_JSON)

    unsafe = await api_client.get("/api/v1/media/covers/..")
    assert unsafe.status_code == 404

    settings = _settings(tmp_path)
    storage = FilesystemCoverStorage(settings.media)
    await storage.save("elden-ring", JPEG)
    found = await api_client.get("/api/v1/media/covers/elden-ring")
    assert found.status_code == 200
    assert found.content == JPEG
    assert found.headers["content-type"] == "image/jpeg"
    assert found.headers["cache-control"] == settings.media.covers_cache_control
