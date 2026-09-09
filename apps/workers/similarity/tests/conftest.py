from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from games_intel.db.engine import async_database_url, create_engine, create_session_factory
from games_intel.db.migrate import upgrade_head
from games_intel.settings import Settings

_TRUNCATE_SQL = """
TRUNCATE TABLE
    similar_games,
    game_platforms,
    ingestion_items,
    daily_processed_slugs,
    processed_events,
    outbox,
    worker_heartbeats,
    external_page_cache,
    adapter_health,
    ingestion_runs,
    ingestion_cursors,
    games
RESTART IDENTITY CASCADE
"""


def _external_database_url() -> str | None:
    raw = os.environ.get("GAMES_INTEL_TEST_DATABASE_URL", "").strip()
    return raw or None


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    external = _external_database_url()
    if external:
        yield async_database_url(external)
        return

    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError as exc:
        pytest.skip(f"testcontainers is required for database tests: {exc}")

    try:
        with PostgresContainer("pgvector/pgvector:pg16") as postgres:
            yield async_database_url(postgres.get_connection_url())
    except Exception as exc:
        pytest.skip(f"PostgreSQL 16 with pgvector is required: {exc}")


@pytest.fixture(scope="session")
def migrated_url(postgres_url: str) -> str:
    upgrade_head(database_url=postgres_url)
    return postgres_url


@pytest.fixture
async def engine(migrated_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(Settings(), url=migrated_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
async def session(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as db_session:
        yield db_session
        await db_session.rollback()
    async with engine.begin() as connection:
        await connection.execute(text(_TRUNCATE_SQL))
