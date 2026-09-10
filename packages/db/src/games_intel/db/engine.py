from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from games_intel.settings import Settings

logger = logging.getLogger("games_intel.db.engine")


def async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    prefixes = (
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
        "postgresql://",
        "postgres://",
    )
    for prefix in prefixes:
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url.removeprefix(prefix)
    return url


def create_engine(settings: Settings, *, url: str | None = None) -> AsyncEngine:
    database_url = url if url is not None else settings.database.url.get_secret_value()
    if not database_url:
        msg = "database.url is empty"
        raise ValueError(msg)
    # Do not register pgvector.asyncpg codecs: SQLAlchemy VECTOR.bind_processor
    # already emits text "[1,2,...]". The asyncpg codec expects a list and
    # double-encodes that string, which breaks embedding writes.
    return create_async_engine(
        async_database_url(database_url),
        pool_size=settings.database.pool_size,
        pool_timeout=settings.database.pool_timeout_seconds,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    session = factory()
    try:
        yield session
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    finally:
        await session.close()


_EMBEDDING_DIM_SQL = """
SELECT format_type(a.atttypid, a.atttypmod)
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = 'games'
AND a.attname = 'embedding' AND a.attnum > 0
"""


async def is_database_ready(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("database not ready error_type=%s", type(exc).__name__)
        return False


async def assert_embedding_dimension(engine: AsyncEngine, expected: int) -> None:
    """Fail fast when pgvector column width disagrees with embeddings.vector_dim."""
    async with engine.connect() as connection:
        formatted = (await connection.execute(text(_EMBEDDING_DIM_SQL))).scalar_one_or_none()
    expected_type = f"vector({expected})"
    if formatted != expected_type:
        msg = f"games.embedding is {formatted!r}, expected {expected_type}"
        raise RuntimeError(msg)


SleepFn = Callable[[float], Awaitable[None]]


async def wait_until_database_ready(
    engine: AsyncEngine,
    *,
    attempts: int = 30,
    interval_seconds: float = 2.0,
    sleep: SleepFn | None = None,
) -> bool:
    """Retry readiness so processes survive infra coming up after Docker restart."""
    pause: SleepFn = sleep if sleep is not None else asyncio.sleep
    total = max(1, attempts)
    for attempt in range(total):
        if await is_database_ready(engine):
            return True
        if attempt + 1 < total:
            await pause(interval_seconds)
    return False
