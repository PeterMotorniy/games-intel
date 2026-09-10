from __future__ import annotations

import re

_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,199}$")


def sanitize_slug(slug: str) -> str | None:
    """Reject path traversal and empty/unsafe keys. Safe slugs pass through unchanged."""
    if not slug or ".." in slug or "/" in slug or "\\" in slug or "\0" in slug:
        return None
    if not _SLUG_RE.fullmatch(slug):
        return None
    return slug
