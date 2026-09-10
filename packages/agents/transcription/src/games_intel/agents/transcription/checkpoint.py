from __future__ import annotations

import hashlib
from uuid import UUID

AGENT_NAME = "transcription"
MAX_THREAD_ID_LEN = 255


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
