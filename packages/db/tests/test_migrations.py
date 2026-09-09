from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from games_intel.db.migrate import downgrade_base, upgrade_head
from games_intel.db.models import VECTOR_DIM

EXPECTED_TABLES = {
    "games",
    "game_platforms",
    "similar_games",
    "ingestion_cursors",
    "ingestion_runs",
    "ingestion_items",
    "daily_processed_slugs",
    "processed_events",
    "outbox",
    "worker_heartbeats",
    "external_page_cache",
    "adapter_health",
}

EXPECTED_TIMESTAMPTZ = {
    ("games", "created_at"),
    ("games", "updated_at"),
    ("ingestion_cursors", "updated_at"),
    ("ingestion_runs", "started_at"),
    ("ingestion_runs", "completed_at"),
    ("ingestion_items", "updated_at"),
    ("processed_events", "consumed_at"),
    ("outbox", "created_at"),
    ("outbox", "published_at"),
    ("worker_heartbeats", "observed_at"),
    ("external_page_cache", "fetched_at"),
    ("adapter_health", "opened_at"),
    ("adapter_health", "last_parse_error_at"),
    ("adapter_health", "updated_at"),
}


async def test_alembic_upgrade_creates_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        tables = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                        " AND tablename <> 'alembic_version'"
                    )
                )
            ).all()
        }
    assert EXPECTED_TABLES == tables


async def test_vector_dimension_matches_orm(engine: AsyncEngine) -> None:
    expected = VECTOR_DIM
    async with engine.connect() as connection:
        formatted = (
            await connection.execute(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) "
                    "FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid = a.attrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = 'games' "
                    "AND a.attname = 'embedding' AND a.attnum > 0"
                )
            )
        ).scalar_one()
    assert formatted == f"vector({expected})"


async def test_all_timestamps_are_timestamptz(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT table_name, column_name, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND data_type LIKE 'timestamp%'"
                )
            )
        ).all()
    actual = {(row[0], row[1]) for row in rows}
    assert EXPECTED_TIMESTAMPTZ <= actual
    for _table, _column, data_type in rows:
        assert data_type == "timestamp with time zone"


async def test_no_hnsw_index_in_0001(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        indexes = (
            (
                await connection.execute(
                    text("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public'")
                )
            )
            .scalars()
            .all()
        )
    assert all("hnsw" not in indexdef.lower() for indexdef in indexes)


async def test_no_langgraph_checkpoint_tables(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        names = (
            (
                await connection.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
            )
            .scalars()
            .all()
        )
    assert all("checkpoint" not in name for name in names)


async def test_unique_indexes_exist(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        indexes = {
            row[0]
            for row in (
                await connection.execute(
                    text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = 'public' AND indexdef ILIKE '%UNIQUE%'"
                    )
                )
            ).all()
        }
    assert "uq_ingestion_runs_inflight_page" in indexes
    assert "uq_ingestion_runs_inflight_null_page" in indexes
    assert "uq_processed_events_worker_idempotency_key" in indexes
    assert "pk_processed_events_worker_event" in indexes
    assert "uq_ingestion_items_run_slug_stage" in indexes


async def test_trgm_and_platform_indexes(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        indexes = {
            row[0]
            for row in (
                await connection.execute(
                    text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
                )
            ).all()
        }
    assert "ix_games_title_trgm" in indexes
    assert "ix_game_platforms_platform_code" in indexes
    assert "ix_games_genres_gin" in indexes


def test_downgrade_then_upgrade(migrated_url: str) -> None:
    downgrade_base(database_url=migrated_url)
    upgrade_head(database_url=migrated_url)
