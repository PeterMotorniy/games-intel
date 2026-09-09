from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from games_intel.adapters.metacritic.urls import is_allowed_fetch_url
from games_intel.scrape.metacritic.fetch import FetchResult
from games_intel.settings import Settings
from games_intel.settings.config import MetacriticAdapterSettings

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page, Playwright

REVIEWS_CARD_WAIT_MS = 6_000
CRITIC_REVIEWS_CARD_WAIT_MS = 12_000
ONETRUST_ACCEPT_SELECTOR = "#onetrust-accept-btn-handler"

logger = logging.getLogger("games_intel.scrape.metacritic")


class PlaywrightFetcher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._meta = settings.adapters.metacritic
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._slots = asyncio.Semaphore(max(1, self._meta.pool_size))
        self._nav_lock = asyncio.Lock()
        self._last_nav_at = 0.0

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._meta.headless,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def fetch_html(self, url: str) -> FetchResult:
        self._reject_disallowed(url)
        browser = self._require_browser()
        timeout_ms = self._meta.timeout_seconds * 1000
        async with self._slots:
            await self._wait_delay()
            context = await browser.new_context(
                user_agent=self._meta.user_agent,
                locale=self._meta.locale,
            )
            page = await context.new_page()
            try:
                from playwright.async_api import TimeoutError as PlaywrightTimeout

                try:
                    response = await page.goto(
                        url, timeout=timeout_ms, wait_until="domcontentloaded"
                    )
                except PlaywrightTimeout as exc:
                    from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError

                    raise MetacriticAdapterError("timeout", "navigation timed out") from exc
                await _accept_privacy_banner(page)
                await _wait_for_page_markers(page, self._meta, url)
                status = response.status if response is not None else 0
                body = await page.content()
                content_type = None
                if response is not None:
                    content_type = response.headers.get("content-type")
                return FetchResult(
                    url=url,
                    status=status,
                    body=body,
                    content_type=content_type,
                )
            finally:
                await context.close()

    async def fetch_bytes(self, url: str) -> bytes:
        self._reject_disallowed(url)
        browser = self._require_browser()
        timeout_ms = self._meta.timeout_seconds * 1000
        async with self._slots:
            await self._wait_delay()
            context = await browser.new_context(
                user_agent=self._meta.user_agent,
                locale=self._meta.locale,
            )
            try:
                from playwright.async_api import TimeoutError as PlaywrightTimeout

                try:
                    response = await context.request.get(url, timeout=timeout_ms)
                except PlaywrightTimeout as exc:
                    from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError

                    raise MetacriticAdapterError("timeout", "asset request timed out") from exc
                if not response.ok:
                    msg = f"asset HTTP {response.status}"
                    raise OSError(msg)
                return await response.body()
            finally:
                await context.close()

    def _reject_disallowed(self, url: str) -> None:
        if is_allowed_fetch_url(url, self._meta.base_url):
            return
        from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError

        raise MetacriticAdapterError("unavailable", "refusing fetch to disallowed host")

    def _require_browser(self) -> Browser:
        if self._browser is None:
            msg = "Playwright browser is not started"
            raise RuntimeError(msg)
        return self._browser

    async def _wait_delay(self) -> None:
        async with self._nav_lock:
            delay = _delay_seconds(self._meta, self._settings.retry.jitter_ratio)
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait_for = self._last_nav_at + delay - now
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last_nav_at = loop.time()


async def _wait_for_page_markers(page: Page, meta: MetacriticAdapterSettings, url: str) -> None:
    """Wait for CSR listing/card/reviews markers after DOMContentLoaded."""
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    timeout_ms = min(20_000, max(5_000, meta.timeout_seconds * 1000 // 2))
    if is_reviews_url(url):
        await _wait_for_reviews_page(page, meta, timeout_ms)
        return
    selector = combined_marker_selector(meta)
    if not selector:
        return
    try:
        await page.wait_for_selector(selector, timeout=timeout_ms, state="attached")
    except PlaywrightTimeout:
        logger.warning("page markers not attached before timeout selector=%s", selector)


async def _wait_for_reviews_page(
    page: Page, meta: MetacriticAdapterSettings, timeout_ms: int
) -> None:
    """Filters/score chrome appear before review cards; wait for cards or an empty list."""
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    container = meta.markers.reviews_container
    if container.strip():
        try:
            await page.wait_for_selector(container, timeout=timeout_ms, state="attached")
        except PlaywrightTimeout:
            logger.warning("reviews container not attached before timeout")
            return
    item_selector = reviews_item_selector(meta)
    if not item_selector:
        return
    wait_ms = (
        CRITIC_REVIEWS_CARD_WAIT_MS if "/critic-reviews" in page.url.casefold() else REVIEWS_CARD_WAIT_MS
    )
    try:
        await page.wait_for_selector(item_selector, timeout=wait_ms, state="attached")
    except PlaywrightTimeout:
        logger.info("review cards not attached; treating page as empty reviews")


async def _accept_privacy_banner(page: Page) -> None:
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    try:
        await page.locator(ONETRUST_ACCEPT_SELECTOR).click(timeout=1500)
    except PlaywrightTimeout:
        return


def is_reviews_url(url: str) -> bool:
    lowered = url.casefold()
    return "/critic-reviews" in lowered or "/user-reviews" in lowered


def reviews_item_selector(meta: MetacriticAdapterSettings) -> str:
    parts = (
        meta.selectors.reviews.critic_item,
        meta.selectors.reviews.user_item,
    )
    return ", ".join(part.strip() for part in parts if part.strip())


def combined_marker_selector(meta: MetacriticAdapterSettings) -> str:
    raw = ",".join(
        (
            meta.markers.listing_container,
            meta.markers.card_container,
            meta.markers.reviews_container,
        )
    )
    return ", ".join(part.strip() for part in raw.split(",") if part.strip())


def _delay_seconds(meta: MetacriticAdapterSettings, jitter_ratio: float) -> float:
    base = max(0, meta.min_delay_ms) / 1000
    if base == 0:
        return 0.0
    jitter = max(0.0, jitter_ratio)
    factor = 1 + random.uniform(-jitter, jitter)
    return max(0.0, base * factor)
