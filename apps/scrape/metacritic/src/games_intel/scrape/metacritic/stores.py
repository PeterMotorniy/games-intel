from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.adapters.metacritic.cache import CacheEntry, url_hash
from games_intel.adapters.metacritic.circuit import CircuitSnapshot, Clock, SystemClock
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.page_cache import PageCacheRepository
from games_intel.scrape.metacritic.service import HealthSink

ADAPTER_NAME = "metacritic"


class PostgresPageCache:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock if clock is not None else SystemClock()

    async def get_fresh(self, url: str, *, ttl_seconds: int) -> CacheEntry | None:
        hashed = url_hash(url)
        async with self._session_factory() as session:
            repo = PageCacheRepository(session)
            row = await repo.get_fresh(
                hashed,
                ttl_seconds=ttl_seconds,
                now=self._clock.now(),
            )
            if row is None:
                return None
            return CacheEntry(
                url_hash=row.url_hash,
                fetched_at=row.fetched_at,
                body=row.body,
                content_type=row.content_type,
                http_status=row.http_status,
            )

    async def put(
        self,
        url: str,
        *,
        body: str,
        http_status: int,
        content_type: str | None,
    ) -> CacheEntry:
        hashed = url_hash(url)
        fetched_at = self._clock.now()
        async with self._session_factory() as session:
            repo = PageCacheRepository(session)
            row = await repo.put(
                url_hash=hashed,
                body=body,
                http_status=http_status,
                content_type=content_type,
                fetched_at=fetched_at,
            )
            await session.commit()
            return CacheEntry(
                url_hash=row.url_hash,
                fetched_at=row.fetched_at,
                body=row.body,
                content_type=row.content_type,
                http_status=row.http_status,
            )


class PostgresHealthSink(HealthSink):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def persist(self, snapshot: CircuitSnapshot) -> None:
        async with self._session_factory() as session:
            repo = IngestionRepository(session)
            await repo.upsert_adapter_health(
                adapter_name=ADAPTER_NAME,
                circuit_state=snapshot.state,
                parse_error_streak=snapshot.parse_error_streak,
                opened_at=snapshot.opened_at,
                last_parse_error_at=snapshot.last_parse_error_at,
            )
            await session.commit()
