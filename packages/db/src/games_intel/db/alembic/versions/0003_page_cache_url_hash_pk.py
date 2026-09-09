"""Align external_page_cache primary key to url_hash.

Revision ID: 0003
Revises: 0002

Irreversible: extra cache-key columns from earlier schema are dropped and not restored.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CACHE_COLUMNS = {
    "url_hash",
    "fetched_at",
    "body",
    "content_type",
    "http_status",
}
_HEALTH_COLUMNS = {
    "adapter_name",
    "circuit_state",
    "parse_error_streak",
    "opened_at",
    "last_parse_error_at",
    "updated_at",
}


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    extra_cache = _column_names("external_page_cache") - _CACHE_COLUMNS
    if extra_cache:
        op.execute(
            sa.text(
                """
                DELETE FROM external_page_cache AS older
                USING external_page_cache AS newer
                WHERE older.url_hash = newer.url_hash
                  AND older.ctid <> newer.ctid
                  AND (
                    older.fetched_at < newer.fetched_at
                    OR (
                      older.fetched_at = newer.fetched_at
                      AND older.ctid < newer.ctid
                    )
                  )
                """
            )
        )
        inspector = sa.inspect(op.get_bind())
        pk = inspector.get_pk_constraint("external_page_cache")
        pk_name = pk.get("name")
        if pk_name:
            op.drop_constraint(pk_name, "external_page_cache", type_="primary")
        for column in sorted(extra_cache):
            op.drop_column("external_page_cache", column)
        op.create_primary_key("external_page_cache_pkey", "external_page_cache", ["url_hash"])

    extra_health = _column_names("adapter_health") - _HEALTH_COLUMNS
    for column in sorted(extra_health):
        op.drop_column("adapter_health", column)


def downgrade() -> None:
    return
