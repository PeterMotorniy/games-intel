from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver

from games_intel.settings import Settings

AGENT_NAME = "review_summarizer"
MAX_THREAD_ID_LEN = 255
logger = logging.getLogger("games_intel.agents.review_summarizer")


def build_thread_id(run_id: UUID, metacritic_slug: str) -> str:
    thread_id = f"{run_id}:{metacritic_slug}:{AGENT_NAME}"
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
    """PostgresSaver when database.url is set; otherwise in-memory (tests)."""
    url = settings.database.url.get_secret_value().strip()
    if not url:
        return InMemorySaver(), None

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        cm = AsyncPostgresSaver.from_conn_string(postgres_dsn(url))
        saver = await cm.__aenter__()
        await saver.setup()
    except ImportError:
        logger.warning("psycopg libpq wrapper unavailable; using in-memory checkpointer")
        return InMemorySaver(), None

    async def _close() -> None:
        await cm.__aexit__(None, None, None)

    return saver, _close
