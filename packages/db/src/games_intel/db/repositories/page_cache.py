from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.db.mapping import page_cache_record, utcnow
from games_intel.db.models import ExternalPageCache
from games_intel.db.records import PageCacheRecord


class PageCacheRepository:
    """Sidecar-only HTML cache keyed by url_hash."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, url_hash: str) -> PageCacheRecord | None:
        row = await self._session.get(ExternalPageCache, url_hash)
        if row is None:
            return None
        return page_cache_record(row)

    async def get_fresh(
        self,
        url_hash: str,
        *,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> PageCacheRecord | None:
        row = await self.get(url_hash)
        if row is None:
            return None
        current = now if now is not None else utcnow()
        if current - row.fetched_at >= timedelta(seconds=ttl_seconds):
            return None
        return row

    async def put(
        self,
        *,
        url_hash: str,
        body: str,
        http_status: int,
        content_type: str | None,
        fetched_at: datetime | None = None,
    ) -> PageCacheRecord:
        when = fetched_at if fetched_at is not None else utcnow()
        stmt = (
            insert(ExternalPageCache)
            .values(
                url_hash=url_hash,
                fetched_at=when,
                body=body,
                content_type=content_type,
                http_status=http_status,
            )
            .on_conflict_do_update(
                index_elements=[ExternalPageCache.url_hash],
                set_={
                    "fetched_at": when,
                    "body": body,
                    "content_type": content_type,
                    "http_status": http_status,
                },
            )
            .returning(ExternalPageCache)
        )
        row = (await self._session.scalars(stmt)).one()
        return page_cache_record(row)
