from __future__ import annotations

from pathlib import Path

import pytest

from games_intel.adapters.media.images import cover_media_type, is_valid_cover
from games_intel.adapters.media.slugs import sanitize_slug
from games_intel.adapters.media.storage import FilesystemCoverStorage
from games_intel.settings.config import MediaSettings

JPEG = b"\xff\xd8\xff" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
GARBAGE = b"not-an-image-payload!!!!"


def _storage(tmp_path: Path) -> FilesystemCoverStorage:
    return FilesystemCoverStorage(
        MediaSettings(covers_dir=str(tmp_path), covers_url_prefix="/api/v1/media/covers")
    )


def test_sanitize_rejects_traversal() -> None:
    assert sanitize_slug("elden-ring") == "elden-ring"
    assert sanitize_slug("../etc/passwd") is None
    assert sanitize_slug("foo/../bar") is None
    assert sanitize_slug("foo\\bar") is None
    assert sanitize_slug("..") is None
    assert sanitize_slug("") is None
    assert sanitize_slug("slug with spaces") is None


def test_is_valid_cover_magic() -> None:
    assert is_valid_cover(JPEG)
    assert is_valid_cover(PNG)
    assert cover_media_type(JPEG) == "image/jpeg"
    assert cover_media_type(PNG) == "image/png"
    assert not is_valid_cover(b"")
    assert not is_valid_cover(b"\xff\xd8")
    assert not is_valid_cover(GARBAGE)
    assert cover_media_type(GARBAGE) is None


@pytest.mark.asyncio
async def test_valid_jpeg_saved_and_overwrite_is_idempotent(tmp_path: Path) -> None:
    covers = _storage(tmp_path)
    url = await covers.save("elden-ring", JPEG)
    assert url == "/api/v1/media/covers/elden-ring"
    stored = await covers.load("elden-ring")
    assert stored == JPEG
    second = JPEG + b"\x01"
    url2 = await covers.save("elden-ring", second)
    assert url2 == url
    assert await covers.load("elden-ring") == second


@pytest.mark.asyncio
async def test_valid_png_saved(tmp_path: Path) -> None:
    covers = _storage(tmp_path)
    url = await covers.save("sekiro", PNG)
    assert url == "/api/v1/media/covers/sekiro"
    assert await covers.load("sekiro") == PNG


@pytest.mark.asyncio
async def test_broken_bytes_do_not_write_file(tmp_path: Path) -> None:
    covers = _storage(tmp_path)
    assert await covers.save("bad-cover", GARBAGE) is None
    assert await covers.save("empty", b"") is None
    assert list(tmp_path.iterdir()) == []
    assert await covers.load("bad-cover") is None


@pytest.mark.asyncio
async def test_broken_bytes_remove_previous_file(tmp_path: Path) -> None:
    covers = _storage(tmp_path)
    await covers.save("bloodborne", JPEG)
    assert (tmp_path / "bloodborne").is_file()
    assert await covers.save("bloodborne", GARBAGE) is None
    assert not (tmp_path / "bloodborne").exists()


@pytest.mark.asyncio
async def test_traversal_slug_does_not_escape_dir(tmp_path: Path) -> None:
    covers = _storage(tmp_path)
    outside = tmp_path.parent / "passwd"
    assert await covers.save("../etc/passwd", JPEG) is None
    assert await covers.save("foo/../../etc/passwd", JPEG) is None
    assert covers.resolve_path("../etc/passwd") is None
    assert not outside.exists()
    assert list(tmp_path.iterdir()) == []
