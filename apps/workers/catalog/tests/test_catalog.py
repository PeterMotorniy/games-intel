from __future__ import annotations

import ast
import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.adapters.media.storage import FilesystemCoverStorage
from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.in_process import InProcessMetacriticAdapter
from games_intel.contracts import GameListed, ListedGame, build_cloud_event
from games_intel.contracts.adapters import GameDetails, GetGameInput
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.payloads import PlatformScore
from games_intel.db.records import ReviewsSlice
from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.reviews import GameReviewsRepository
from games_intel.db.types import (
    IngestionItemStatus,
    IngestionRunStatus,
    IngestionStage,
    RunTrigger,
)
from games_intel.kafka.daemon import DaemonConfig, DaemonLoop
from games_intel.kafka.serialization import encode_cloud_event
from games_intel.kafka.source import worker_source
from games_intel.kafka.testing import FakeBroker, FakeConsumer, FakeProducer
from games_intel.kafka.types import IncomingRecord
from games_intel.settings import Settings
from games_intel.settings.config import MediaSettings
from games_intel.workers.catalog.handler import CatalogHandler

PROCESS_DATE = date(2026, 9, 8)
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-0000000000bb")
RUN_ID_2 = UUID("0191c0aa-7e3b-7000-8000-0000000000cc")
SLUG = "elden-ring"
JPEG = b"\xff\xd8\xff" + b"\x00" * 16
GARBAGE = b"not-an-image-payload!!!!"
CATALOG_SRC = Path(__file__).resolve().parents[1] / "src" / "games_intel" / "workers" / "catalog"


def _settings(covers_dir: Path, *, instance_id: str = "catalog-1") -> Settings:
    base = Settings()
    retry = base.retry.model_copy(
        update={"max_attempts": 3, "backoff_base_seconds": 0, "jitter_ratio": 0}
    )
    catalog = base.catalog.model_copy(update={"instance_id": instance_id})
    media = MediaSettings(covers_dir=str(covers_dir), covers_url_prefix="/api/v1/media/covers")
    return base.model_copy(update={"retry": retry, "media": media, "catalog": catalog})


def _details(
    *,
    slug: str = SLUG,
    title: str = "Elden Ring",
    cover_bytes: bytes | None = JPEG,
    video: bool = True,
    developer: str | None = "FromSoftware",
    platforms: list[PlatformScore] | None = None,
) -> GameDetails:
    return GameDetails(
        slug=slug,
        title=title,
        cover_source_url=HttpUrl("https://static.metacritic.com/images/elden-ring.jpg"),
        cover_bytes=cover_bytes,
        developer=developer,
        publisher="Bandai Namco",
        description="An open-world action RPG.",
        video_url=HttpUrl("https://www.youtube.com/watch?v=abc123") if video else None,
        platforms=platforms
        or [
            PlatformScore(platform_code="ps5", metascore=96, userscore=7.8),
            PlatformScore(platform_code="pc", metascore=94, userscore=6.4),
        ],
        genres=["Action", "RPG"],
        release_date=date(2022, 2, 25),
    )


def _listed(
    *,
    event_id: str,
    run_id: UUID = RUN_ID,
    slug: str = SLUG,
    title: str = "Elden Ring",
    position: int = 0,
    settings: Settings | None = None,
) -> CloudEvent[Any]:
    loaded = settings if settings is not None else Settings()
    data = GameListed(
        run_id=run_id,
        process_date=PROCESS_DATE,
        source="new_releases",
        page=None,
        game=ListedGame(
            metacritic_slug=slug,
            title=title,
            listing_url=HttpUrl(f"https://www.metacritic.com/game/{slug}/"),
            position=position,
        ),
    )
    return build_cloud_event(
        loaded,
        loaded.catalog.subscribe_event,
        source=worker_source(loaded, "discovery"),
        subject=slug,
        data=data,
        stage="discovered",
        run_id=run_id,
        event_id=event_id,
        occurred_at=NOW,
    )


def _record(event: CloudEvent[Any], settings: Settings, *, offset: int = 0) -> IncomingRecord:
    return IncomingRecord(
        topic=settings.event_name(settings.catalog.subscribe_event),
        partition=0,
        offset=offset,
        key=event.subject,
        value=encode_cloud_event(event),
    )


async def _no_sleep(_delay: float) -> None:
    return None


def _see_committed(session: AsyncSession) -> None:
    session.expire_all()


async def _seed(
    session: AsyncSession,
    *,
    run_id: UUID = RUN_ID,
    slug: str = SLUG,
    title: str = "Elden Ring",
    extra: list[tuple[str, str]] | None = None,
    critic_summary: str | None = None,
) -> None:
    ingestion = IngestionRepository(session)
    catalog = GameCatalogRepository(session)
    await ingestion.create_run(
        process_date=PROCESS_DATE,
        source="new_releases",
        page=None,
        limit=20,
        trigger=RunTrigger.cron,
        run_id=run_id,
        status=IngestionRunStatus.completed,
    )
    games = [(slug, title), *(extra or ())]
    for index, (game_slug, game_title) in enumerate(games):
        game_id, _ = await catalog.ensure_game_stub(
            metacritic_slug=game_slug,
            title=game_title,
            listing_url=f"https://www.metacritic.com/game/{game_slug}/",
        )
        await ingestion.upsert_item(
            run_id=run_id,
            metacritic_slug=game_slug,
            process_date=PROCESS_DATE,
            stage=IngestionStage.discovered,
            status=IngestionItemStatus.completed,
            game_id=game_id,
            event_id=f"discovered-seed-{index}",
        )
    if critic_summary is not None:
        await GameReviewsRepository(session).update_reviews(
            ReviewsSlice(
                metacritic_slug=slug,
                critic_likes=("combat",),
                critic_dislikes=("performance",),
                critic_summary=critic_summary,
                user_likes=("exploration",),
                user_dislikes=("difficulty",),
                user_summary="Harsh but fair.",
            )
        )
    await session.commit()
    session.expire_all()


def _loop(
    session_factory: async_sessionmaker[AsyncSession],
    handler: CatalogHandler,
    settings: Settings,
    *,
    instance_id: str = "catalog-1",
) -> tuple[DaemonLoop, FakeBroker, FakeConsumer]:
    broker = FakeBroker()
    consumer = FakeConsumer(broker, (settings.event_name(settings.catalog.subscribe_event),))
    producer = FakeProducer(broker)
    loop = DaemonLoop(
        settings,
        DaemonConfig(
            worker_type="catalog",
            instance_id=instance_id,
            stage_name=settings.catalog.stage_name,
            subscribe_event_key=settings.catalog.subscribe_event,
            lease_seconds=settings.catalog.lease_seconds,
        ),
        consumer=consumer,
        producer=producer,
        session_factory=session_factory,
        handler=handler,
        sleep=_no_sleep,
    )
    return loop, broker, consumer


def _handler(
    tmp_path: Path, port: InProcessMetacriticAdapter, *, instance_id: str = "catalog-1"
) -> tuple[CatalogHandler, Settings, FilesystemCoverStorage]:
    settings = _settings(tmp_path, instance_id=instance_id)
    covers = FilesystemCoverStorage(settings.media)
    return CatalogHandler(settings, port, covers), settings, covers


async def test_fake_get_game_persists_catalog_slice(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session, critic_summary="Great combat.")
    port = InProcessMetacriticAdapter(games={SLUG: _details()})
    handler, settings, covers = _handler(tmp_path, port)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_listed(event_id="cat-happy", settings=settings), settings))
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.title == "Elden Ring"
    assert game.cover_url == "/api/v1/media/covers/elden-ring"
    assert game.cover_source_url == "https://static.metacritic.com/images/elden-ring.jpg"
    assert game.developer == "FromSoftware"
    assert game.publisher == "Bandai Namco"
    assert game.genres == ("Action", "RPG")
    assert game.release_date == date(2022, 2, 25)
    assert game.description == "An open-world action RPG."
    assert game.video_url == "https://www.youtube.com/watch?v=abc123"
    assert game.critic_summary == "Great combat."
    codes = {p.platform_code: p for p in game.platforms}
    assert codes["ps5"].metascore == 96
    assert codes["ps5"].userscore == Decimal("7.8")
    assert codes["pc"].metascore == 94
    stored = await covers.load(SLUG)
    assert stored == JPEG
    rows = await OutboxRepository(session).claim("catalog", limit=10)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["type"] == settings.event_name("game_cataloged")
    assert payload["source"] == "urn:games-intel:worker:catalog"
    data = payload["data"]
    assert data["cover_url"] == "/api/v1/media/covers/elden-ring"
    assert not str(data["cover_url"]).startswith("https://static.metacritic.com")
    assert data["cover_source_url"] == "https://static.metacritic.com/images/elden-ring.jpg"
    assert data["genres"] == ["Action", "RPG"]
    assert data["release_date"] == "2022-02-25"
    assert {p["platform_code"] for p in data["platforms"]} == {"ps5", "pc"}
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    daily = await IngestionRepository(session).list_daily_processed_slugs(PROCESS_DATE)
    assert SLUG in daily
    discovered = await IngestionRepository(session).get_item(
        RUN_ID, SLUG, IngestionStage.discovered
    )
    assert discovered is not None
    assert discovered.status is IngestionItemStatus.completed


async def test_two_listed_games_are_two_cataloged_events(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    second = "sekiro"
    await _seed(session, extra=[(second, "Sekiro")])
    port = InProcessMetacriticAdapter(
        games={SLUG: _details(), second: _details(slug=second, title="Sekiro")}
    )
    handler, settings, _covers = _handler(tmp_path, port)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_listed(event_id="cat-listed-a", settings=settings), settings, offset=0)
    )
    await loop.process_record(
        _record(
            _listed(
                event_id="cat-listed-b",
                slug=second,
                title="Sekiro",
                position=1,
                settings=settings,
            ),
            settings,
            offset=1,
        )
    )
    _see_committed(session)
    rows = await OutboxRepository(session).claim("catalog", limit=10)
    assert len(rows) == 2
    slugs = {row.payload["data"]["metacritic_slug"] for row in rows}
    assert slugs == {SLUG, second}
    traces = {row.payload.get("traceparent") for row in rows}
    assert None not in traces
    assert len(traces) == 2
    first_item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    second_item = await IngestionRepository(session).get_item(
        RUN_ID, second, IngestionStage.cataloged
    )
    assert first_item is not None and first_item.status is IngestionItemStatus.completed
    assert second_item is not None and second_item.status is IngestionItemStatus.completed


async def test_catalog_does_not_clobber_critic_summary(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session, critic_summary="Keep me.")
    port = InProcessMetacriticAdapter(games={SLUG: _details()})
    handler, settings, _covers = _handler(tmp_path, port)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_listed(event_id="cat-reviews", settings=settings), settings))
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.critic_summary == "Keep me."
    assert game.user_summary == "Harsh but fair."
    assert game.cover_url == "/api/v1/media/covers/elden-ring"


async def test_404_fails_item_without_retry_or_dlq(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(
        errors={"get_game:elden-ring": MetacriticAdapterError("not_found", "gone")}
    )
    handler, settings, _covers = _handler(tmp_path, port)
    loop, broker, consumer = _loop(session_factory, handler, settings)
    record = _record(_listed(event_id="cat-404", settings=settings), settings)
    await loop.process_record(record)
    get_calls = [call for call in port.calls if call[0] == "get_game"]
    assert len(get_calls) == 1
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    assert item is not None
    assert item.status is IngestionItemStatus.failed
    assert item.error_type == "NotFoundError"
    discovered = await IngestionRepository(session).get_item(
        RUN_ID, SLUG, IngestionStage.discovered
    )
    assert discovered is not None
    assert discovered.status is IngestionItemStatus.completed
    run = await IngestionRepository(session).get_run(RUN_ID)
    assert run is not None
    assert run.status is IngestionRunStatus.completed
    assert await OutboxRepository(session).claim("catalog", limit=10) == ()
    assert consumer.committed[(record.topic, 0)] == 1
    assert (
        settings.event_name("dlq") not in broker.topics
        or not broker.topics[settings.event_name("dlq")]
    )
    daily = await IngestionRepository(session).list_daily_processed_slugs(PROCESS_DATE)
    assert SLUG in daily


async def test_timeout_retries_then_catalogs(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    port = _FlakyPort(_details(), fail_times=2)
    handler, settings, _covers = _handler(tmp_path, port)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_listed(event_id="cat-timeout", settings=settings), settings)
    await loop.process_record(record)
    assert port.attempts == 3
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    assert consumer.committed[(record.topic, 0)] == 1
    rows = await OutboxRepository(session).claim("catalog", limit=10)
    assert len(rows) == 1


async def test_timeout_on_one_game_does_not_fail_another(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    second = "sekiro"
    await _seed(session, extra=[(second, "Sekiro")])
    port = _FailSlugPort(
        {SLUG: _details(), second: _details(slug=second, title="Sekiro")},
        fail_slug=SLUG,
    )
    handler, settings, _covers = _handler(tmp_path, port)
    loop, _, consumer = _loop(session_factory, handler, settings)
    first = _record(_listed(event_id="cat-timeout-a", settings=settings), settings, offset=0)
    second_record = _record(
        _listed(
            event_id="cat-timeout-b",
            slug=second,
            title="Sekiro",
            position=1,
            settings=settings,
        ),
        settings,
        offset=1,
    )
    await loop.process_record(first)
    await loop.process_record(second_record)
    _see_committed(session)
    ingestion = IngestionRepository(session)
    failed = await ingestion.get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    ok = await ingestion.get_item(RUN_ID, second, IngestionStage.cataloged)
    bogus = await ingestion.get_item(RUN_ID, str(RUN_ID), IngestionStage.cataloged)
    assert failed is not None and failed.status is IngestionItemStatus.failed
    assert failed.error_type == "TransientError"
    assert ok is not None and ok.status is IngestionItemStatus.completed
    assert bogus is None
    assert consumer.committed[(first.topic, 0)] == 2
    rows = await OutboxRepository(session).claim("catalog", limit=10)
    assert {row.payload["data"]["metacritic_slug"] for row in rows} == {second}


async def test_kill_during_catalog_get_retries_from_warm_cache(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    port = _CacheThenCrashPort(_details())
    handler, settings, _covers = _handler(tmp_path, port)
    loop, _, consumer = _loop(session_factory, handler, settings)
    record = _record(_listed(event_id="cat-cache-kill", settings=settings), settings)
    await loop.process_record(record)
    assert port.fetches == 1
    assert port.cache_hits == 1
    _see_committed(session)
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    assert consumer.committed[(record.topic, 0)] == 1
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.publisher == "Bandai Namco"


async def test_missing_optional_fields_complete_with_nulls(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    details = _details(cover_bytes=None, video=False, developer=None)
    port = InProcessMetacriticAdapter(games={SLUG: details})
    handler, settings, covers = _handler(tmp_path, port)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_listed(event_id="cat-optional", settings=settings), settings)
    )
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.cover_url is None
    assert game.video_url is None
    assert game.developer is None
    assert game.publisher == "Bandai Namco"
    assert await covers.load(SLUG) is None
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    assert item is not None
    assert item.status is IngestionItemStatus.completed
    rows = await OutboxRepository(session).claim("catalog", limit=10)
    assert rows[0].payload["data"]["cover_url"] is None
    assert rows[0].payload["data"]["video_url"] is None


async def test_broken_cover_bytes_null_url_completed(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(games={SLUG: _details(cover_bytes=GARBAGE)})
    handler, settings, covers = _handler(tmp_path, port)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(
        _record(_listed(event_id="cat-bad-cover", settings=settings), settings)
    )
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert game.cover_url is None
    assert await covers.load(SLUG) is None
    item = await IngestionRepository(session).get_item(RUN_ID, SLUG, IngestionStage.cataloged)
    assert item is not None
    assert item.status is IngestionItemStatus.completed


async def test_replay_discovered_is_catalog_noop(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(games={SLUG: _details()})
    handler, settings, _covers = _handler(tmp_path, port)
    loop, _, consumer = _loop(session_factory, handler, settings)
    event = _listed(event_id="cat-idem", settings=settings)
    await loop.process_record(_record(event, settings, offset=0))
    await loop.process_record(_record(event, settings, offset=1))
    get_calls = [call for call in port.calls if call[0] == "get_game"]
    assert len(get_calls) == 1
    _see_committed(session)
    rows = await OutboxRepository(session).claim("catalog", limit=10)
    assert len(rows) == 1
    assert consumer.committed[(settings.event_name("game_listed"), 0)] == 2


async def test_two_replicas_one_persist(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    port = InProcessMetacriticAdapter(games={SLUG: _details()})
    handler_a, settings_a, _c1 = _handler(tmp_path, port, instance_id="catalog-a")
    handler_b, settings_b, _c2 = _handler(tmp_path, port, instance_id="catalog-b")
    loop_a, _, _ = _loop(session_factory, handler_a, settings_a, instance_id="catalog-a")
    loop_b, _, _ = _loop(session_factory, handler_b, settings_b, instance_id="catalog-b")
    event = _listed(event_id="cat-replica", settings=settings_a)
    await asyncio.gather(
        loop_a.process_record(_record(event, settings_a, offset=0)),
        loop_b.process_record(_record(event, settings_b, offset=1)),
    )
    get_calls = [call for call in port.calls if call[0] == "get_game"]
    assert 1 <= len(get_calls) <= 2
    _see_committed(session)
    rows = await OutboxRepository(session).claim("catalog", limit=10)
    assert len(rows) == 1
    keys = {row.idempotency_key for row in rows}
    expected = (
        f"{settings_a.event_name('game_cataloged')}:{RUN_ID}:{SLUG}:{settings_a.catalog.stage_name}"
    )
    assert expected in keys


async def test_platforms_replace_atomic_on_new_run(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed(session)
    first = _details(
        platforms=[
            PlatformScore(platform_code="ps5", metascore=96, userscore=7.8),
            PlatformScore(platform_code="pc", metascore=94, userscore=6.4),
        ]
    )
    port = InProcessMetacriticAdapter(games={SLUG: first})
    handler, settings, _covers = _handler(tmp_path, port)
    loop, _, _ = _loop(session_factory, handler, settings)
    await loop.process_record(_record(_listed(event_id="cat-p1", settings=settings), settings))
    await IngestionRepository(session).create_run(
        process_date=PROCESS_DATE,
        source="browse",
        page=1,
        limit=20,
        trigger=RunTrigger.manual,
        run_id=RUN_ID_2,
        status=IngestionRunStatus.completed,
    )
    await session.commit()
    port._games[SLUG] = _details(
        platforms=[PlatformScore(platform_code="ns2", metascore=91, userscore=8.2)]
    )
    event2 = _listed(event_id="cat-p2", run_id=RUN_ID_2, settings=settings)
    await loop.process_record(_record(event2, settings, offset=2))
    _see_committed(session)
    game = await GameCatalogRepository(session).get_by_slug(SLUG)
    assert game is not None
    assert [p.platform_code for p in game.platforms] == ["ns2"]
    assert game.platforms[0].metascore == 91
    assert game.critic_summary is None


async def test_catalog_topics_and_group_come_from_settings(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert settings.catalog.subscribe_event == "game_listed"
    assert settings.catalog.publish_event == "game_cataloged"
    assert settings.catalog.stage_name == "cataloged"
    assert settings.consumer_group_id(settings.catalog.consumer_group) == "games-intel.catalog"
    assert settings.event_name(settings.catalog.subscribe_event) == "game.listed"
    assert settings.event_name(settings.catalog.publish_event) == "game.cataloged"


def test_catalog_does_not_import_langchain_or_selectors() -> None:
    for path in CATALOG_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "langchain" not in node.module
                assert "langgraph" not in node.module
                assert "playwright" not in node.module
                assert "workers.reviews" not in node.module
                assert "workers.similarity" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "langchain" not in alias.name
                    assert "playwright" not in alias.name
        text = path.read_text(encoding="utf-8")
        assert "c-productHero" not in text
        assert "c-gameDetails" not in text


class _FlakyPort(InProcessMetacriticAdapter):
    def __init__(self, details: GameDetails, *, fail_times: int) -> None:
        super().__init__(games={details.slug: details})
        self._fail_times = fail_times
        self.attempts = 0

    async def get_game(self, inp: GetGameInput) -> GameDetails:
        self.attempts += 1
        if self.attempts <= self._fail_times:
            raise MetacriticAdapterError("timeout", "transient")
        return await super().get_game(inp)


class _FailSlugPort(InProcessMetacriticAdapter):
    def __init__(self, games: dict[str, GameDetails], *, fail_slug: str) -> None:
        super().__init__(games=games)
        self._fail_slug = fail_slug

    async def get_game(self, inp: GetGameInput) -> GameDetails:
        if inp.slug == self._fail_slug:
            raise MetacriticAdapterError("timeout", "transient")
        return await super().get_game(inp)


class _CacheThenCrashPort(InProcessMetacriticAdapter):
    def __init__(self, details: GameDetails) -> None:
        super().__init__(games={details.slug: details})
        self.fetches = 0
        self.cache_hits = 0
        self._warm: GameDetails | None = None

    async def get_game(self, inp: GetGameInput) -> GameDetails:
        if self._warm is not None:
            self.cache_hits += 1
            return self._warm
        self.fetches += 1
        details = await super().get_game(inp)
        self._warm = details
        raise MetacriticAdapterError("timeout", "killed after GET")
