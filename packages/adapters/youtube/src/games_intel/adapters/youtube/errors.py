from __future__ import annotations

from games_intel.adapters.youtube.exceptions import YoutubeAdapterError


def map_ytdlp_error(exc: BaseException) -> YoutubeAdapterError:
    """Classify yt-dlp failures. Returned message never includes URLs or payloads."""
    text = f"{type(exc).__name__} {exc}".casefold()
    if "429" in text or "too many requests" in text:
        return YoutubeAdapterError("rate_limited", "youtube rate limited")
    if "timed out" in text or "timeout" in text or "timedout" in text:
        return YoutubeAdapterError("timeout", "youtube request timed out")
    return YoutubeAdapterError("unavailable", "youtube extractor unavailable")
