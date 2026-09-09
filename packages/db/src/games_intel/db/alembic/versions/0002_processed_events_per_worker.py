"""Scope processed_events uniqueness by worker_type.

Revision ID: 0002
Revises: 0001

Catalog, Reviews and LetsPlay all consume the same game.discovered CloudEvent.
Uniqueness must be per worker_type so replicas still no-op while sibling
stages of the same game can all run.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("processed_events_pkey", "processed_events", type_="primary")
    op.drop_constraint("uq_processed_events_idempotency_key", "processed_events", type_="unique")
    op.create_primary_key(
        "pk_processed_events_worker_event",
        "processed_events",
        ["worker_type", "event_id"],
    )
    op.create_unique_constraint(
        "uq_processed_events_worker_idempotency_key",
        "processed_events",
        ["worker_type", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_processed_events_worker_idempotency_key",
        "processed_events",
        type_="unique",
    )
    op.drop_constraint("pk_processed_events_worker_event", "processed_events", type_="primary")
    op.create_primary_key("processed_events_pkey", "processed_events", ["event_id"])
    op.create_unique_constraint(
        "uq_processed_events_idempotency_key",
        "processed_events",
        ["idempotency_key"],
    )
