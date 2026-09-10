from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from games_intel.adapters.metacritic.cache import MemoryPageCache
from games_intel.adapters.metacritic.circuit import CircuitBreaker
from games_intel.adapters.metacritic.client import SidecarMetacriticClient
from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.contracts.adapters import (
    CanaryParseInput,
    GetGameInput,
    GetReviewsInput,
    ListNewReleasesInput,
)
from games_intel.scrape.metacritic.app import create_app
from games_intel.scrape.metacritic.browser import (
    CRITIC_REVIEWS_CARD_WAIT_MS,
    LISTING_CARD_WAIT_MS,
    REVIEWS_CARD_WAIT_MS,
    combined_marker_selector,
    is_reviews_url,
    listing_wait_selector,
    reviews_item_selector,
)
from games_intel.scrape.metacritic.fetch import FetchResult, ScriptedFetcher
from games_intel.scrape.metacritic.service import MemoryHealthSink, ScrapeService
from games_intel.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "metacritic"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 12


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _settings(**meta_updates: object) -> Settings:
    base = Settings()
    meta = base.adapters.metacritic.model_copy(
        update={
            "canary_enabled": False,
            "min_delay_ms": 0,
            "cache_ttl_seconds": 3600,
            "circuit_fail_threshold": 3,
            "circuit_open_seconds": 600,
            **meta_updates,
        }
    )
    adapters = base.adapters.model_copy(update={"metacritic": meta})
    return base.model_copy(update={"adapters": adapters})


def _service(
    settings: Settings,
    fetcher: ScriptedFetcher,
    *,
    clock: FakeClock | None = None,
    download_covers: bool = True,
) -> tuple[ScrapeService, MemoryHealthSink]:
    clock = clock or FakeClock(datetime(2026, 9, 8, 12, 0, tzinfo=UTC))
    health = MemoryHealthSink()
    service = ScrapeService(
        settings.adapters.metacritic,
        fetcher=fetcher,
        cache=MemoryPageCache(clock=clock),
        circuit=CircuitBreaker(
            fail_threshold=settings.adapters.metacritic.circuit_fail_threshold,
            open_seconds=settings.adapters.metacritic.circuit_open_seconds,
            clock=clock,
        ),
        health=health,
        download_covers=download_covers,
    )
    return service, health


def _page(path: str, html: str, status: int = 200) -> FetchResult:
    return FetchResult(url=f"https://www.metacritic.com{path}", status=status, body=html)


async def test_cache_hit_skips_network() -> None:
    settings = _settings()
    fetcher = ScriptedFetcher(
        html={
            "/game/elden-ring/": _page("/game/elden-ring/", _html("card.html")),
        },
        binaries={"elden-ring.jpg": JPEG},
    )
    service, _health = _service(settings, fetcher)
    first = await service.get_game(GetGameInput(slug="elden-ring"))
    second = await service.get_game(GetGameInput(slug="elden-ring"))
    assert first.title == second.title == "Elden Ring"
    assert fetcher.html_calls == [
        "https://www.metacritic.com/game/elden-ring/",
    ]


async def test_stale_cache_refetches() -> None:
    settings = _settings(cache_ttl_seconds=10)
    clock = FakeClock(datetime(2026, 9, 8, 12, 0, tzinfo=UTC))
    fetcher = ScriptedFetcher(
        html={"/game/elden-ring/": _page("/game/elden-ring/", _html("card.html"))},
        binaries={"elden-ring.jpg": JPEG},
    )
    service, _health = _service(settings, fetcher, clock=clock)
    await service.get_game(GetGameInput(slug="elden-ring"))
    clock.advance(11)
    await service.get_game(GetGameInput(slug="elden-ring"))
    assert len(fetcher.html_calls) == 2


async def test_circuit_opens_after_parse_errors() -> None:
    settings = _settings(circuit_fail_threshold=3)
    fetcher = ScriptedFetcher(
        html={"/game/": _page("/game/", _html("empty_dom.html"))},
    )
    service, health = _service(settings, fetcher)
    for _ in range(3):
        with pytest.raises(MetacriticAdapterError) as exc_info:
            await service.list_new_releases(ListNewReleasesInput(limit=20))
        assert exc_info.value.code == "parse_error"
    with pytest.raises(MetacriticAdapterError) as exc_info:
        await service.list_new_releases(ListNewReleasesInput(limit=20))
    assert exc_info.value.code == "circuit_open"
    assert health.latest is not None
    assert health.latest.state == "open"
    assert len(fetcher.html_calls) == 1


async def test_listing_does_not_rerun_canary() -> None:
    settings = _settings(canary_enabled=True, canary_slug="elden-ring")
    fetcher = ScriptedFetcher(
        html={
            "/game/elden-ring/": _page("/game/elden-ring/", _html("empty_dom.html")),
            "/game/": _page("/game/", _html("new_releases.html")),
        }
    )
    service, _health = _service(settings, fetcher, download_covers=False)
    listing = await service.list_new_releases(ListNewReleasesInput(limit=20))
    assert listing.items
    assert fetcher.html_calls == ["https://www.metacritic.com/game/"]


async def test_invalid_cover_bytes_not_returned() -> None:
    settings = _settings()
    fetcher = ScriptedFetcher(
        html={"/game/elden-ring/": _page("/game/elden-ring/", _html("card.html"))},
        binaries={"elden-ring.jpg": b"not-an-image-file!!"},
    )
    service, _health = _service(settings, fetcher)
    details = await service.get_game(GetGameInput(slug="elden-ring"))
    assert details.cover_bytes is None
    assert details.title == "Elden Ring"


async def test_valid_cover_bytes_attached() -> None:
    settings = _settings()
    fetcher = ScriptedFetcher(
        html={"/game/elden-ring/": _page("/game/elden-ring/", _html("card.html"))},
        binaries={"elden-ring.jpg": JPEG},
    )
    service, _health = _service(settings, fetcher)
    details = await service.get_game(GetGameInput(slug="elden-ring"))
    assert details.cover_bytes == JPEG


async def test_offsite_cover_url_is_not_fetched() -> None:
    settings = _settings()
    html = _html("card.html").replace(
        "https://static.metacritic.com/images/elden-ring.jpg",
        "http://127.0.0.1/secret.jpg",
    )
    fetcher = ScriptedFetcher(
        html={"/game/elden-ring/": _page("/game/elden-ring/", html)},
        binaries={"http://127.0.0.1/secret.jpg": JPEG, "secret.jpg": JPEG},
    )
    service, _health = _service(settings, fetcher)
    details = await service.get_game(GetGameInput(slug="elden-ring"))
    assert details.cover_bytes is None
    assert fetcher.binary_calls == []


async def test_healthz_and_sidecar_client_same_dto() -> None:
    settings = _settings(sidecar_base_url="http://scrape-metacritic")
    fetcher = ScriptedFetcher(
        html={"/game/elden-ring/": _page("/game/elden-ring/", _html("card.html"))},
        binaries={"elden-ring.jpg": JPEG},
    )
    service, _health = _service(settings, fetcher)
    app = create_app(settings, service=service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://scrape") as raw:
        health = await raw.get("/healthz")
        assert health.status_code == 200
        body = health.json()
        assert body["status"] == "ok"
        assert body["circuit_state"] == "closed"
        client = SidecarMetacriticClient(settings, client=raw)
        details = await client.get_game(GetGameInput(slug="elden-ring"))
        assert details.title == "Elden Ring"
        assert details.cover_bytes == JPEG
        canary = await client.canary_parse(CanaryParseInput(slug="elden-ring"))
        assert canary.ok is True


async def test_timeout_maps_to_adapter_error() -> None:
    settings = _settings()
    fetcher = ScriptedFetcher(
        html={"/game/": TimeoutError("slow")},
    )
    service, _health = _service(settings, fetcher)
    with pytest.raises(MetacriticAdapterError) as exc_info:
        await service.list_new_releases(ListNewReleasesInput(limit=20))
    assert exc_info.value.code == "timeout"


async def test_reviews_fixture_via_sidecar_no_html() -> None:
    settings = _settings()
    fetcher = ScriptedFetcher(
        html={
            "/game/elden-ring/critic-reviews/": _page(
                "/game/elden-ring/critic-reviews/", _html("reviews.html")
            ),
            "/game/elden-ring/user-reviews/": _page(
                "/game/elden-ring/user-reviews/", _html("reviews.html")
            ),
        }
    )
    service, _health = _service(settings, fetcher, download_covers=False)
    critics = await service.get_critic_reviews(
        GetReviewsInput(slug="elden-ring", limit=50, max_chars=8000)
    )
    users = await service.get_user_reviews(
        GetReviewsInput(slug="elden-ring", limit=50, max_chars=8000)
    )
    assert len(critics.items) == 2
    assert critics.items[0].excerpt
    assert "<" not in critics.items[0].excerpt
    assert len(users.items) == 1
    assert fetcher.html_calls == [
        "https://www.metacritic.com/game/elden-ring/critic-reviews/",
        "https://www.metacritic.com/game/elden-ring/user-reviews/",
    ]


async def test_empty_reviews_skip_parse_error() -> None:
    settings = _settings()
    fetcher = ScriptedFetcher(
        html={
            "/game/elden-ring/critic-reviews/": _page(
                "/game/elden-ring/critic-reviews/", _html("empty_reviews.html")
            )
        }
    )
    service, _health = _service(settings, fetcher, download_covers=False)
    batch = await service.get_critic_reviews(
        GetReviewsInput(slug="elden-ring", limit=50, max_chars=8000)
    )
    assert batch.items == []
    assert batch.truncated is False


async def test_reviews_timeout_is_transient_code() -> None:
    settings = _settings()
    fetcher = ScriptedFetcher(
        html={"/game/elden-ring/critic-reviews/": TimeoutError("slow reviews")},
    )
    service, _health = _service(settings, fetcher, download_covers=False)
    with pytest.raises(MetacriticAdapterError) as exc_info:
        await service.get_critic_reviews(
            GetReviewsInput(slug="elden-ring", limit=50, max_chars=8000)
        )
    assert exc_info.value.code == "timeout"


async def test_sidecar_client_reviews_same_dto() -> None:
    settings = _settings(sidecar_base_url="http://scrape-metacritic")
    fetcher = ScriptedFetcher(
        html={
            "/game/elden-ring/critic-reviews/": _page(
                "/game/elden-ring/critic-reviews/", _html("reviews.html")
            )
        }
    )
    service, _health = _service(settings, fetcher, download_covers=False)
    app = create_app(settings, service=service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://scrape") as raw:
        client = SidecarMetacriticClient(settings, client=raw)
        batch = await client.get_critic_reviews(
            GetReviewsInput(slug="elden-ring", limit=1, max_chars=8000)
        )
        assert len(batch.items) == 1
        assert batch.truncated is True


def test_combined_marker_selector_includes_odyssey_and_legacy() -> None:
    selector = combined_marker_selector(Settings().adapters.metacritic)
    assert '[data-testid="product-hero"]' in selector or "[data-testid='product-hero']" in selector
    assert ".c-productHero" in selector
    assert "new-game-release-carousel" in selector
    assert ".c-pageProductHome" in selector
    assert "filter-results" in selector


def test_listing_wait_selector_uses_browse_container() -> None:
    meta = Settings().adapters.metacritic
    browse = listing_wait_selector(
        meta, "https://www.metacritic.com/browse/game/all/all/all-time/new/?page=2"
    )
    home = listing_wait_selector(meta, "https://www.metacritic.com/game/")
    card = listing_wait_selector(meta, "https://www.metacritic.com/game/elden-ring/")
    assert "filter-results" in browse
    assert "new-game-release-carousel" not in browse
    assert "new-game-release-carousel" in home
    assert "filter-results" not in home
    assert "product-hero" in card
    assert LISTING_CARD_WAIT_MS <= 10_000


def test_reviews_url_and_item_selector() -> None:
    meta = Settings().adapters.metacritic
    assert is_reviews_url("https://www.metacritic.com/game/valheim/critic-reviews/")
    assert is_reviews_url("https://www.metacritic.com/game/valheim/user-reviews/")
    assert not is_reviews_url("https://www.metacritic.com/game/valheim/")
    selector = reviews_item_selector(meta)
    assert "review-card" in selector
    assert "c-siteReview_critic" in selector
    assert REVIEWS_CARD_WAIT_MS <= 8_000
    assert CRITIC_REVIEWS_CARD_WAIT_MS >= REVIEWS_CARD_WAIT_MS
    assert CRITIC_REVIEWS_CARD_WAIT_MS <= 15_000
