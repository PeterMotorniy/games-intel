from __future__ import annotations

import hashlib

from games_intel.db.records import SimilarityGame


def canonical_embedding_text(game: SimilarityGame, *, include_reviews: bool) -> str:
    """Skip empty fields. Never substitute n/a."""
    parts: list[str] = []
    _append(parts, "title", game.title)
    _append(parts, "developer", game.developer)
    _append(parts, "publisher", game.publisher)
    genres = ", ".join(item.strip() for item in game.genres if item.strip())
    _append(parts, "genres", genres or None)
    _append(parts, "description", game.description)
    if include_reviews:
        _append(parts, "critic_summary", game.critic_summary)
        _append(parts, "user_summary", game.user_summary)
    return "\n".join(parts)


def embedding_input_hash(text: str, *, model: str, vector_dim: int) -> str:
    payload = f"{text}\0{model}\0{vector_dim}".encode()
    return hashlib.sha256(payload).hexdigest()


def _append(parts: list[str], label: str, value: str | None) -> None:
    if value is None:
        return
    stripped = value.strip()
    if not stripped:
        return
    parts.append(f"{label}: {stripped}")
