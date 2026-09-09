from __future__ import annotations

import re

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"


def is_safe_video_id(video_id: str) -> bool:
    return bool(_VIDEO_ID_RE.fullmatch(video_id))


def watch_url(video_id: str) -> str:
    return _WATCH_URL.format(video_id=video_id)
