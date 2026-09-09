from __future__ import annotations

from uuid import UUID

AGENT_NAME = "transcription"
MAX_THREAD_ID_LEN = 255


def build_thread_id(run_id: UUID, metacritic_slug: str) -> str:
    thread_id = f"{run_id}:{metacritic_slug}:{AGENT_NAME}"
    if len(thread_id) >= MAX_THREAD_ID_LEN:
        msg = f"thread_id length {len(thread_id)} exceeds {MAX_THREAD_ID_LEN - 1}"
        raise ValueError(msg)
    return thread_id
