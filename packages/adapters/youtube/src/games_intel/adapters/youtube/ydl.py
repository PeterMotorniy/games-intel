from __future__ import annotations

from typing import Any


def ydl_options(timeout_seconds: int, **extra: Any) -> dict[str, Any]:
    """Shared yt-dlp options. Android client first: web player JS is slow and brittle."""
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": timeout_seconds,
        "retries": 2,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    options.update(extra)
    return options
