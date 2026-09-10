from __future__ import annotations

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"
_WEBP = b"WEBP"
_RIFF = b"RIFF"
_MIN_BYTES = 12


def is_valid_cover(data: bytes) -> bool:
    """Accept jpeg/png (and sidecar-compatible gif/webp/avif). Reject empty/truncated/garbage."""
    return cover_media_type(data) is not None


def cover_media_type(data: bytes) -> str | None:
    """MIME type for a stored cover, or None if bytes are not a supported image."""
    if len(data) < _MIN_BYTES:
        return None
    if data.startswith(_JPEG):
        return "image/jpeg"
    if data.startswith(_PNG):
        return "image/png"
    if data.startswith(_GIF87) or data.startswith(_GIF89):
        return "image/gif"
    if data.startswith(_RIFF) and data[8:12] == _WEBP:
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis", b"mif1"}:
        return "image/avif"
    return None
