from __future__ import annotations

from pathlib import Path
from typing import Protocol


class CoverStorage(Protocol):
    """Local cover files keyed by metacritic_slug. API later serves GET prefix/slug."""

    def public_url(self, slug: str) -> str: ...

    def resolve_path(self, slug: str) -> Path | None: ...

    async def save(self, slug: str, data: bytes) -> str | None: ...

    async def load(self, slug: str) -> bytes | None: ...
