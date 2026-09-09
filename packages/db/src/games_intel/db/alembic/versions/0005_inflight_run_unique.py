"""One in-flight ingestion run per source/page, including manual ticks.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_ingestion_runs_cron_active_page", table_name="ingestion_runs")
    op.drop_index("uq_ingestion_runs_cron_active_null_page", table_name="ingestion_runs")
    op.create_index(
        "uq_ingestion_runs_inflight_page",
        "ingestion_runs",
        ["process_date", "source", "page"],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'running') AND page IS NOT NULL"),
    )
    op.create_index(
        "uq_ingestion_runs_inflight_null_page",
        "ingestion_runs",
        ["process_date", "source"],
        unique=True,
        postgresql_where=sa.text("status IN ('requested', 'running') AND page IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ingestion_runs_inflight_page", table_name="ingestion_runs")
    op.drop_index("uq_ingestion_runs_inflight_null_page", table_name="ingestion_runs")
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
