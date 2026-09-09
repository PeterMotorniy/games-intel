"""Initial schema: extensions, domain, pipeline, outbox, cache.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Historical embedding width before local nomic-embed-text (768) in 0004.
_INITIAL_VECTOR_DIM = 1536


def _vector_dim() -> int:
    return _INITIAL_VECTOR_DIM


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("metacritic_slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("listing_url", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("cover_source_url", sa.Text(), nullable=True),
        sa.Column("developer", sa.Text(), nullable=True),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column(
            "genres",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("critic_likes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("critic_dislikes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("critic_summary", sa.Text(), nullable=True),
        sa.Column("user_likes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("user_dislikes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("user_summary", sa.Text(), nullable=True),
        sa.Column("letsplay_status", sa.Text(), nullable=True),
        sa.Column("letsplay_video_url", sa.Text(), nullable=True),
        sa.Column("letsplay_video_title", sa.Text(), nullable=True),
        sa.Column("letsplay_view_count", sa.Integer(), nullable=True),
        sa.Column("letsplay_conclusion", sa.Text(), nullable=True),
        sa.Column("letsplay_highlights", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("embedding", Vector(_vector_dim()), nullable=True),
        sa.Column("embedding_input_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "letsplay_status IS NULL OR letsplay_status IN"
            " ('ok', 'no_video', 'transcript_unavailable', 'quota_exceeded')",
            name="ck_games_letsplay_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metacritic_slug"),
    )
    op.create_index(
        "ix_games_title_trgm",
        "games",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_games_genres_gin", "games", ["genres"], unique=False, postgresql_using="gin"
    )

    op.create_table(
        "game_platforms",
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("platform_code", sa.Text(), nullable=False),
        sa.Column("metascore", sa.Integer(), nullable=True),
        sa.Column("userscore", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("game_id", "platform_code"),
    )
    op.create_index("ix_game_platforms_platform_code", "game_platforms", ["platform_code"])

    op.create_table(
        "similar_games",
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("similar_game_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("score_vector", sa.Double(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.CheckConstraint("game_id <> similar_game_id", name="ck_similar_games_no_self"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["similar_game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("game_id", "similar_game_id"),
    )

    op.create_table(
        "ingestion_cursors",
        sa.Column("process_date", sa.Date(), nullable=False),
        sa.Column("new_releases_done", sa.Boolean(), nullable=False),
        sa.Column("last_browse_page", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("process_date"),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("process_date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('requested', 'running', 'completed', 'failed')",
            name="ck_ingestion_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_ingestion_runs_cron_active_page",
        "ingestion_runs",
        ["process_date", "source", "page"],
        unique=True,
        postgresql_where=sa.text("status <> 'failed' AND trigger = 'cron' AND page IS NOT NULL"),
    )
    op.create_index(
        "uq_ingestion_runs_cron_active_null_page",
        "ingestion_runs",
        ["process_date", "source"],
        unique=True,
        postgresql_where=sa.text("status <> 'failed' AND trigger = 'cron' AND page IS NULL"),
    )

    op.create_table(
        "ingestion_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=True),
        sa.Column("metacritic_slug", sa.Text(), nullable=False),
        sa.Column("process_date", sa.Date(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'degraded')",
            name="ck_ingestion_items_status",
        ),
        sa.CheckConstraint(
            "stage IN ('discovered', 'cataloged', 'reviews', 'letsplay', 'similar')",
            name="ck_ingestion_items_stage",
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["ingestion_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "metacritic_slug",
            "stage",
            name="uq_ingestion_items_run_slug_stage",
        ),
    )

    op.create_table(
        "daily_processed_slugs",
        sa.Column("process_date", sa.Date(), nullable=False),
        sa.Column("metacritic_slug", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("process_date", "metacritic_slug"),
    )

    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("worker_type", sa.Text(), nullable=False),
        sa.Column("instance_id", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_processed_events_idempotency_key"),
    )

    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("producer", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("partition_key", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_type", sa.Text(), nullable=False),
        sa.Column("instance_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_subject", sa.Text(), nullable=True),
        sa.Column("processed_ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lag_hint", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_type", "instance_id"),
    )

    op.create_table(
        "external_page_cache",
        sa.Column("url_hash", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("url_hash"),
    )

    op.create_table(
        "adapter_health",
        sa.Column("adapter_name", sa.Text(), nullable=False),
        sa.Column("circuit_state", sa.Text(), nullable=False),
        sa.Column("parse_error_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_parse_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("adapter_name"),
    )


def downgrade() -> None:
    op.drop_table("adapter_health")
    op.drop_table("external_page_cache")
    op.drop_table("worker_heartbeats")
    op.drop_table("outbox")
    op.drop_table("processed_events")
    op.drop_table("daily_processed_slugs")
    op.drop_table("ingestion_items")
    op.drop_index("uq_ingestion_runs_cron_active_null_page", table_name="ingestion_runs")
    op.drop_index("uq_ingestion_runs_cron_active_page", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("ingestion_cursors")
    op.drop_table("similar_games")
    op.drop_index("ix_game_platforms_platform_code", table_name="game_platforms")
    op.drop_table("game_platforms")
    op.drop_index("ix_games_genres_gin", table_name="games")
    op.drop_index("ix_games_title_trgm", table_name="games")
    op.drop_table("games")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
