from __future__ import annotations

import re

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_safe_video_id(video_id: str) -> bool:
    return bool(_VIDEO_ID_RE.fullmatch(video_id))
