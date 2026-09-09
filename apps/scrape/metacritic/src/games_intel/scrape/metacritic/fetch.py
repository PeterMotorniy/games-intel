from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    status: int
    body: str
    content_type: str | None = "text/html"


class PageFetcher(Protocol):
    async def fetch_html(self, url: str) -> FetchResult: ...

    async def fetch_bytes(self, url: str) -> bytes: ...


_T = TypeVar("_T")


class ScriptedFetcher:
    """Deterministic fetcher for unit tests. No network."""

    def __init__(
        self,
        html: dict[str, FetchResult | Exception] | None = None,
        binaries: dict[str, bytes | Exception] | None = None,
    ) -> None:
        self.html = dict(html or {})
        self.binaries = dict(binaries or {})
        self.html_calls: list[str] = []
        self.binary_calls: list[str] = []

    async def fetch_html(self, url: str) -> FetchResult:
        self.html_calls.append(url)
        result = self._lookup(self.html, url)
        if isinstance(result, Exception):
            raise result
        return result

    async def fetch_bytes(self, url: str) -> bytes:
        self.binary_calls.append(url)
        result = self._lookup(self.binaries, url)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise FileNotFoundError(url)
        return result

    def _lookup(self, table: Mapping[str, _T], url: str) -> _T:
        if url in table:
            return table[url]
        path = urlparse(url).path
        if path in table:
            return table[path]
        for key, value in table.items():
            if path.rstrip("/") == str(key).rstrip("/"):
                return value
            if url.endswith(key) and "/" not in str(key).strip("/"):
                return value
        raise KeyError(url)
