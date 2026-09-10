from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from games_intel.adapters.media.images import is_valid_cover
from games_intel.adapters.media.port import CoverStorage
from games_intel.adapters.media.slugs import sanitize_slug
from games_intel.settings import Settings
from games_intel.settings.config import MediaSettings

logger = logging.getLogger("games_intel.adapters.media")


class FilesystemCoverStorage:
    """Volume-backed covers. Never logs image bytes. Unsafe slugs do not leave covers_dir."""

    def __init__(self, settings: MediaSettings) -> None:
        self._dir = Path(settings.covers_dir)
        self._prefix = settings.covers_url_prefix.rstrip("/")

    def public_url(self, slug: str) -> str:
        safe = sanitize_slug(slug)
        if safe is None:
            msg = "refusing public_url for unsafe slug"
            raise ValueError(msg)
        return f"{self._prefix}/{safe}"

    def resolve_path(self, slug: str) -> Path | None:
        safe = sanitize_slug(slug)
        if safe is None:
            return None
        path = (self._dir / safe).resolve()
        root = self._dir.resolve()
        if path != root and root not in path.parents:
            return None
        if path.parent != root:
            return None
        return path

    async def save(self, slug: str, data: bytes) -> str | None:
        return await asyncio.to_thread(self._save_sync, slug, data)

    async def load(self, slug: str) -> bytes | None:
        return await asyncio.to_thread(self._load_sync, slug)

    def _save_sync(self, slug: str, data: bytes) -> str | None:
        path = self.resolve_path(slug)
        if path is None:
            logger.warning("cover slug rejected")
            return None
        if not is_valid_cover(data):
            if path.exists() and path.is_file():
                path.unlink()
            logger.warning("cover bytes rejected slug=%s size=%s", path.name, len(data))
            return None
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return self.public_url(slug)

    def _load_sync(self, slug: str) -> bytes | None:
        path = self.resolve_path(slug)
        if path is None or not path.is_file():
            return None
        return path.read_bytes()


def create_cover_storage(settings: Settings) -> CoverStorage:
    return FilesystemCoverStorage(settings.media)
