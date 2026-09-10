"""Outbox claim lease, item leases, HNSW, monitor indexes.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str | None] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outbox", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox", sa.Column("claimed_by", sa.Text(), nullable=True))
    op.add_column(
        "outbox", sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_outbox_unpublished_producer",
        "outbox",
        ["producer", "id"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.add_column(
        "ingestion_items",
        sa.Column("claimed_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("ingestion_items", sa.Column("claimed_by", sa.Text(), nullable=True))
    op.create_index(
        "ix_ingestion_items_process_date",
        "ingestion_items",
        ["process_date"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_items_slug_stage_updated",
        "ingestion_items",
        ["metacritic_slug", "stage", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_similar_games_similar_game_id",
        "similar_games",
        ["similar_game_id"],
        unique=False,
    )
    op.create_index(
        "uq_similar_games_game_rank",
        "similar_games",
        ["game_id", "rank"],
        unique=True,
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_games_embedding_hnsw "
            "ON games USING hnsw (embedding vector_cosine_ops) "
            "WHERE embedding IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_games_embedding_hnsw"))
    op.drop_index("uq_similar_games_game_rank", table_name="similar_games")
    op.drop_index("ix_similar_games_similar_game_id", table_name="similar_games")
    op.drop_index("ix_ingestion_items_slug_stage_updated", table_name="ingestion_items")
    op.drop_index("ix_ingestion_items_process_date", table_name="ingestion_items")
    op.drop_column("ingestion_items", "claimed_by")
    op.drop_column("ingestion_items", "claimed_until")
    op.drop_index("ix_outbox_unpublished_producer", table_name="outbox")
    op.drop_column("outbox", "claim_expires_at")
    op.drop_column("outbox", "claimed_by")
    op.drop_column("outbox", "claimed_at")
