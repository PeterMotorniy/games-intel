from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver

from games_intel.settings import Settings

AGENT_NAME = "letsplay_analyst"
MAX_THREAD_ID_LEN = 255
logger = logging.getLogger("games_intel.agents.letsplay_analyst")


def input_digest(*chunks: str) -> str:
    hasher = hashlib.sha256()
    for chunk in chunks:
        hasher.update(chunk.encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()[:16]


def build_thread_id(run_id: UUID, metacritic_slug: str, digest: str = "") -> str:
    parts = [str(run_id), metacritic_slug, AGENT_NAME]
    if digest:
        parts.append(digest)
    thread_id = ":".join(parts)
    if len(thread_id) >= MAX_THREAD_ID_LEN:
        msg = f"thread_id length {len(thread_id)} exceeds {MAX_THREAD_ID_LEN - 1}"
        raise ValueError(msg)
    return thread_id


def postgres_dsn(database_url: str) -> str:
    dsn = database_url.strip()
    replacements = (
        ("postgresql+asyncpg://", "postgresql://"),
        ("postgresql+psycopg2://", "postgresql://"),
        ("postgresql+psycopg://", "postgresql://"),
        ("postgres://", "postgresql://"),
    )
    for prefix, replacement in replacements:
        if dsn.startswith(prefix):
            return replacement + dsn.removeprefix(prefix)
    return dsn


async def open_checkpointer(
    settings: Settings,
) -> tuple[Any, Callable[[], Awaitable[None]] | None]:
    """PostgresSaver when database.url is set; in-memory only when URL is empty (tests)."""
    url = settings.database.url.get_secret_value().strip()
    if not url:
        return InMemorySaver(), None

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:
        msg = "Postgres checkpointer required when database.url is set"
        raise RuntimeError(msg) from exc

    cm = AsyncPostgresSaver.from_conn_string(postgres_dsn(url))
    saver = await cm.__aenter__()
    await saver.setup()

    async def _close() -> None:
        await cm.__aexit__(None, None, None)

    return saver, _close
