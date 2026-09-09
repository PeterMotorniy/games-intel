from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import HttpUrl, ValidationError

from games_intel.adapters.youtube.duration import coerce_duration_seconds, coerce_view_count
from games_intel.adapters.youtube.errors import map_ytdlp_error
from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.ids import is_safe_video_id, watch_url
from games_intel.adapters.youtube.ydl import ydl_options
from games_intel.contracts.adapters import VideoHit

_SEARCH_CAP = 50
_FETCH_MULTIPLIER = 3


class VideoSearch(Protocol):
    def search(self, query: str, max_results: int) -> list[VideoHit]: ...


class FakeVideoSearch:
    def __init__(
        self,
        items: Sequence[VideoHit] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self._items = list(items or ())
        self._error = error
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int) -> list[VideoHit]:
        self.calls.append((query, max_results))
        if self._error is not None:
            raise self._error
        return list(self._items)


class YtDlpVideoSearch:
    """YouTube search via yt-dlp InnerTube (no Data API key)."""

    def __init__(self, timeout_seconds: int) -> None:
        self._timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int) -> list[VideoHit]:
        try:
            import yt_dlp
        except ImportError as exc:
            raise YoutubeAdapterError("unavailable", "youtube extractor missing") from exc
        fetch_n = min(_SEARCH_CAP, max(max_results * _FETCH_MULTIPLIER, max_results, 1))
        options = ydl_options(
            self._timeout_seconds,
            skip_download=True,
            extract_flat="in_playlist",
            playlistend=fetch_n,
            ignoreerrors=True,
            noplaylist=False,
        )
        url = f"ytsearch{fetch_n}:{query}"
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                payload = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise map_ytdlp_error(exc) from exc
        return _hits_from_search_payload(payload)


def _hits_from_search_payload(payload: object) -> list[VideoHit]:
    if not isinstance(payload, dict):
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        hit = hit_from_extractor_entry(payload)
        return [hit] if hit is not None else []
    hits: list[VideoHit] = []
    for entry in entries:
        hit = hit_from_extractor_entry(entry)
        if hit is not None:
            hits.append(hit)
    return hits


def hit_from_extractor_entry(entry: object) -> VideoHit | None:
    if not isinstance(entry, dict):
        return None
    video_id = _entry_video_id(entry)
    if video_id is None or not is_safe_video_id(video_id):
        return None
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    duration = coerce_duration_seconds(entry.get("duration"))
    if duration is None:
        return None
    channel = _entry_channel(entry)
    try:
        return VideoHit(
            video_id=video_id,
            title=title,
            view_count=coerce_view_count(entry.get("view_count")),
            duration_seconds=duration,
            channel_title=channel,
            url=HttpUrl(watch_url(video_id)),
        )
    except ValidationError:
        return None


def _entry_video_id(entry: dict[str, Any]) -> str | None:
    raw = entry.get("id")
    if isinstance(raw, str) and raw:
        return raw
    raw = entry.get("url")
    if isinstance(raw, str) and is_safe_video_id(raw):
        return raw
    return None


def _entry_channel(entry: dict[str, Any]) -> str | None:
    for key in ("channel", "uploader", "channel_id"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None
