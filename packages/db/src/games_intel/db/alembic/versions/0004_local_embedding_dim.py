"""Resize games.embedding for local nomic-embed-text (768).

Revision ID: 0004
Revises: 0003

Irreversible: previous 1536-d vectors are discarded; Similarity rebuilds from Ollama.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_LOCAL_VECTOR_DIM = 768
_INITIAL_VECTOR_DIM = 1536


def upgrade() -> None:
    op.execute("UPDATE games SET embedding = NULL, embedding_input_hash = NULL")
    op.execute(f"ALTER TABLE games ALTER COLUMN embedding TYPE vector({_LOCAL_VECTOR_DIM})")


def downgrade() -> None:
    op.execute("UPDATE games SET embedding = NULL, embedding_input_hash = NULL")
    op.execute(f"ALTER TABLE games ALTER COLUMN embedding TYPE vector({_INITIAL_VECTOR_DIM})")
