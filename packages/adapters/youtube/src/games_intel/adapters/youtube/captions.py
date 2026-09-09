from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from games_intel.adapters.youtube.exceptions import YoutubeAdapterError

_UNAVAILABLE_TYPE_NAMES = frozenset(
    {
        "CouldNotRetrieveTranscript",
        "NoTranscriptFound",
        "TranscriptsDisabled",
        "VideoUnavailable",
        "IpBlocked",
        "RequestBlocked",
        "AgeRestricted",
        "PoTokenRequired",
        "InvalidVideoId",
        "YouTubeRequestFailed",
    }
)


@dataclass(frozen=True, slots=True)
class CaptionsText:
    text: str
    language: str | None


class CaptionsFetcher(Protocol):
    def fetch(self, video_id: str) -> CaptionsText | None: ...


class YoutubeTranscriptFetcher:
    """youtube-transcript-api backend. Network happens only when fetch is called."""

    def fetch(self, video_id: str) -> CaptionsText | None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as exc:
            raise YoutubeAdapterError("unavailable", "youtube transcript backend missing") from exc
        try:
            return _fetch_captions(YouTubeTranscriptApi, video_id)
        except Exception as exc:
            if _is_unavailable_transcript(exc):
                return None
            raise YoutubeAdapterError("unavailable", "youtube captions request failed") from exc


class FakeCaptionsFetcher:
    def __init__(self, mapping: Mapping[str, CaptionsText | None] | None = None) -> None:
        self._mapping = dict(mapping or {})
        self.calls: list[str] = []

    def fetch(self, video_id: str) -> CaptionsText | None:
        self.calls.append(video_id)
        if video_id not in self._mapping:
            return None
        return self._mapping[video_id]


def _fetch_captions(api_cls: Any, video_id: str) -> CaptionsText | None:
    api = api_cls()
    fetched = getattr(api, "fetch", None)
    if callable(fetched):
        payload = fetched(video_id)
        language = getattr(payload, "language_code", None) or getattr(payload, "language", None)
        pieces: list[str] = []
        for snippet in payload:
            text = getattr(snippet, "text", None)
            if isinstance(text, str) and text.strip():
                pieces.append(text.strip())
            elif isinstance(snippet, dict):
                raw = snippet.get("text")
                if isinstance(raw, str) and raw.strip():
                    pieces.append(raw.strip())
        joined = " ".join(pieces).strip()
        if not joined:
            return None
        return CaptionsText(text=joined, language=str(language) if language else None)
    get_transcript = getattr(api_cls, "get_transcript", None)
    if callable(get_transcript):
        rows = get_transcript(video_id)
        pieces = []
        for row in rows:
            if isinstance(row, dict):
                raw = row.get("text")
                if isinstance(raw, str) and raw.strip():
                    pieces.append(raw.strip())
        joined = " ".join(pieces).strip()
        if not joined:
            return None
        return CaptionsText(text=joined, language=None)
    raise YoutubeAdapterError("unavailable", "youtube transcript backend missing fetch")


def _is_unavailable_transcript(exc: BaseException) -> bool:
    for cls in type(exc).__mro__:
        if cls.__name__ in _UNAVAILABLE_TYPE_NAMES:
            return True
    return False
