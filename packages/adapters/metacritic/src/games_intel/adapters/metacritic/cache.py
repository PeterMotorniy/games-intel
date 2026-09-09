from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from games_intel.adapters.metacritic.circuit import Clock, SystemClock
from games_intel.adapters.metacritic.urls import canonicalize_url


@dataclass(frozen=True, slots=True)
class CacheEntry:
    url_hash: str
    fetched_at: datetime
    body: str
    content_type: str | None
    http_status: int


class PageCache(Protocol):
    async def get_fresh(self, url: str, *, ttl_seconds: int) -> CacheEntry | None: ...

    async def put(
        self,
        url: str,
        *,
        body: str,
        http_status: int,
        content_type: str | None,
    ) -> CacheEntry: ...


def url_hash(url: str) -> str:
    canonical = canonicalize_url(url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class MemoryPageCache:
    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock if clock is not None else SystemClock()
        self._entries: dict[str, CacheEntry] = {}

    async def get_fresh(self, url: str, *, ttl_seconds: int) -> CacheEntry | None:
        entry = self._entries.get(url_hash(url))
        if entry is None:
            return None
        if self._clock.now() - entry.fetched_at >= timedelta(seconds=ttl_seconds):
            return None
        return entry

    async def put(
        self,
        url: str,
        *,
        body: str,
        http_status: int,
        content_type: str | None,
    ) -> CacheEntry:
        hashed = url_hash(url)
        entry = CacheEntry(
            url_hash=hashed,
            fetched_at=self._clock.now(),
            body=body,
            content_type=content_type,
            http_status=http_status,
        )
        self._entries[hashed] = entry
        return entry
