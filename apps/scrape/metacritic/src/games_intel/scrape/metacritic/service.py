from __future__ import annotations

import logging
from typing import Literal

from games_intel.adapters.metacritic.cache import PageCache
from games_intel.adapters.metacritic.circuit import CircuitBreaker, CircuitSnapshot
from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.images import is_valid_image
from games_intel.adapters.metacritic.parser import parse_game, parse_listing, parse_reviews
from games_intel.adapters.metacritic.urls import (
    browse_url,
    critic_reviews_url,
    game_url,
    is_allowed_fetch_url,
    join_url,
    user_reviews_url,
)
from games_intel.contracts.adapters import (
    CanaryParseInput,
    CanaryParseResult,
    GameDetails,
    GameListing,
    GetGameInput,
    GetReviewsInput,
    ListBrowsePageInput,
    ListNewReleasesInput,
    ReviewBatch,
)
from games_intel.scrape.metacritic.fetch import PageFetcher
from games_intel.settings.config import MetacriticAdapterSettings

logger = logging.getLogger("games_intel.scrape.metacritic")

_HTTP_ERROR: dict[int, tuple[str, str]] = {
    403: ("unavailable", "forbidden or challenge"),
    404: ("not_found", "resource not found"),
    429: ("rate_limited", "rate limited"),
}


class HealthSink:
    async def persist(self, snapshot: CircuitSnapshot) -> None:
        return None


class MemoryHealthSink(HealthSink):
    def __init__(self) -> None:
        self.latest: CircuitSnapshot | None = None

    async def persist(self, snapshot: CircuitSnapshot) -> None:
        self.latest = snapshot


class ScrapeService:
    def __init__(
        self,
        settings: MetacriticAdapterSettings,
        *,
        fetcher: PageFetcher,
        cache: PageCache,
        circuit: CircuitBreaker,
        health: HealthSink | None = None,
        download_covers: bool = True,
    ) -> None:
        self._settings = settings
        self._fetcher = fetcher
        self._cache = cache
        self._circuit = circuit
        self._health = health if health is not None else HealthSink()
        self._download_covers = download_covers

    @property
    def circuit(self) -> CircuitBreaker:
        return self._circuit

    async def list_new_releases(self, inp: ListNewReleasesInput) -> GameListing:
        self._ensure_circuit()
        url = join_url(self._settings.base_url, self._settings.new_releases_path)
        html = await self._html(url)
        try:
            listing = parse_listing(
                html, self._settings, source="new_releases", page=None, limit=inp.limit
            )
        except MetacriticAdapterError as exc:
            await self._on_adapter_error(exc)
            raise
        await self._on_success()
        return listing

    async def list_browse_page(self, inp: ListBrowsePageInput) -> GameListing:
        self._ensure_circuit()
        url = browse_url(
            self._settings.base_url,
            self._settings.browse_path,
            self._settings.browse_page_query_param,
            inp.page,
        )
        html = await self._html(url)
        try:
            listing = parse_listing(
                html, self._settings, source="browse", page=inp.page, limit=inp.limit
            )
        except MetacriticAdapterError as exc:
            await self._on_adapter_error(exc)
            raise
        await self._on_success()
        return listing

    async def get_game(self, inp: GetGameInput) -> GameDetails:
        self._ensure_circuit()
        url = game_url(self._settings.base_url, inp.slug)
        html = await self._html(url)
        try:
            details = parse_game(html, self._settings, inp.slug)
        except MetacriticAdapterError as exc:
            await self._on_adapter_error(exc)
            raise
        await self._on_success()
        if self._download_covers:
            details = await self._attach_cover(details)
        return details

    async def get_critic_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        return await self._reviews(inp, kind="critic")

    async def get_user_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        return await self._reviews(inp, kind="user")

    async def canary_parse(self, inp: CanaryParseInput) -> CanaryParseResult:
        self._ensure_circuit()
        url = game_url(self._settings.base_url, inp.slug)
        try:
            html = await self._html(url)
            parse_game(html, self._settings, inp.slug)
        except MetacriticAdapterError as exc:
            await self._on_adapter_error(exc)
            return CanaryParseResult(ok=False, error_code=exc.code)
        await self._on_success()
        return CanaryParseResult(ok=True, error_code=None)

    async def _reviews(
        self, inp: GetReviewsInput, *, kind: Literal["critic", "user"]
    ) -> ReviewBatch:
        self._ensure_circuit()
        builder = critic_reviews_url if kind == "critic" else user_reviews_url
        html = await self._html(builder(self._settings.base_url, inp.slug))
        try:
            batch = parse_reviews(
                html, self._settings, kind=kind, limit=inp.limit, max_chars=inp.max_chars
            )
        except MetacriticAdapterError as exc:
            await self._on_adapter_error(exc)
            raise
        await self._on_success()
        return batch

    def _ensure_circuit(self) -> None:
        if not self._circuit.allow_request():
            raise MetacriticAdapterError("circuit_open", "metacritic circuit is open")

    async def _html(self, url: str) -> str:
        cached = await self._cache.get_fresh(url, ttl_seconds=self._settings.cache_ttl_seconds)
        if cached is not None:
            self._raise_http(cached.http_status)
            return cached.body
        try:
            fetched = await self._fetcher.fetch_html(url)
        except TimeoutError as exc:
            raise MetacriticAdapterError("timeout", "fetch timed out") from exc
        self._raise_http(fetched.status)
        if fetched.status == 200:
            await self._cache.put(
                url,
                body=fetched.body,
                http_status=fetched.status,
                content_type=fetched.content_type,
            )
        return fetched.body

    def _raise_http(self, status: int) -> None:
        if status == 200:
            return
        mapped = _HTTP_ERROR.get(status)
        if mapped is not None:
            raise MetacriticAdapterError(mapped[0], mapped[1])  # type: ignore[arg-type]
        if status >= 500 or status == 0:
            raise MetacriticAdapterError("unavailable", f"upstream HTTP {status}")
        raise MetacriticAdapterError("unavailable", f"upstream HTTP {status}")

    async def _attach_cover(self, details: GameDetails) -> GameDetails:
        if details.cover_source_url is None:
            return details
        url = str(details.cover_source_url)
        if not is_allowed_fetch_url(url, self._settings.base_url):
            logger.warning("cover url refused slug=%s", details.slug)
            return details.model_copy(update={"cover_bytes": None})
        try:
            raw = await self._fetcher.fetch_bytes(url)
        except Exception:
            logger.warning("cover download failed slug=%s", details.slug)
            return details.model_copy(update={"cover_bytes": None})
        if not is_valid_image(raw):
            logger.warning("cover bytes rejected slug=%s", details.slug)
            return details.model_copy(update={"cover_bytes": None})
        return details.model_copy(update={"cover_bytes": raw})

    async def _on_success(self) -> None:
        snapshot = self._circuit.record_success()
        await self._health.persist(snapshot)

    async def _on_adapter_error(self, exc: MetacriticAdapterError) -> None:
        if exc.code != "parse_error":
            return
        snapshot = self._circuit.record_parse_error()
        await self._health.persist(snapshot)
