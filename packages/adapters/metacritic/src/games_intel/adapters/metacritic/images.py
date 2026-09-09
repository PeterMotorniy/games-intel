from __future__ import annotations

_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"
_WEBP = b"WEBP"
_RIFF = b"RIFF"


def is_valid_image(data: bytes) -> bool:
    if len(data) < 12:
        return False
    if data.startswith(_JPEG) or data.startswith(_PNG):
        return True
    if data.startswith(_GIF87) or data.startswith(_GIF89):
        return True
    if data.startswith(_RIFF) and data[8:12] == _WEBP:
        return True
    if data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis", b"mif1"}:
        return True
    return False
