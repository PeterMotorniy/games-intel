from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from games_intel.adapters.youtube.errors import map_ytdlp_error
from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.ids import is_safe_video_id, watch_url
from games_intel.adapters.youtube.ydl import ydl_options

_LANG_PREFERENCE = ("en", "en-orig", "en-us", "en-gb", "ru")
_FORMAT_PREFERENCE = ("json3", "vtt", "srv3", "srv1")
_NON_CAPTION_LANGUAGES = frozenset({"live_chat", "danmaku"})
_VTT_TS = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+")
_VTT_CUE = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class CaptionsText:
    text: str
    language: str | None


class CaptionsFetcher(Protocol):
    def fetch(self, video_id: str) -> CaptionsText | None: ...


class YtDlpCaptionsFetcher:
    """Captions from yt-dlp InnerTube tracks (manual, then auto). No Data API."""

    def __init__(self, timeout_seconds: int) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch(self, video_id: str) -> CaptionsText | None:
        if not is_safe_video_id(video_id):
            return None
        try:
            import yt_dlp
        except ImportError as exc:
            raise YoutubeAdapterError("unavailable", "youtube extractor missing") from exc
        options = ydl_options(
            self._timeout_seconds,
            skip_download=True,
            noplaylist=True,
        )
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(watch_url(video_id), download=False)
                chosen = select_caption_track(info)
                if chosen is None:
                    return None
                language, ext, track_url = chosen
                raw = ydl.urlopen(track_url).read()
        except YoutubeAdapterError:
            raise
        except Exception as exc:
            if _is_missing_captions(exc):
                return None
            raise map_ytdlp_error(exc) from exc
        text = parse_caption_payload(ext, raw)
        if not text:
            return None
        return CaptionsText(text=text, language=language)


class FakeCaptionsFetcher:
    def __init__(self, mapping: Mapping[str, CaptionsText | None] | None = None) -> None:
        self._mapping = dict(mapping or {})
        self.calls: list[str] = []

    def fetch(self, video_id: str) -> CaptionsText | None:
        self.calls.append(video_id)
        if video_id not in self._mapping:
            return None
        return self._mapping[video_id]


def select_caption_track(info: object) -> tuple[str, str, str] | None:
    if not isinstance(info, dict):
        return None
    for bucket_key in ("subtitles", "automatic_captions"):
        bucket = info.get(bucket_key)
        picked = _pick_from_bucket(bucket)
        if picked is not None:
            return picked
    return None


def parse_caption_payload(ext: str, raw: bytes) -> str:
    body = raw.decode("utf-8", errors="replace")
    if _looks_like_html(body):
        return ""
    lowered = ext.casefold()
    if lowered == "json3":
        return _parse_json3(body)
    if lowered in {"vtt", "srv3", "srv1"}:
        return _parse_vtt(body)
    return " ".join(body.split()).strip()


def _pick_from_bucket(bucket: object) -> tuple[str, str, str] | None:
    if not isinstance(bucket, dict):
        return None
    languages = _ordered_languages(bucket)
    for language in languages:
        tracks = bucket.get(language)
        picked = _pick_format(language, tracks)
        if picked is not None:
            return picked
    return None


def _ordered_languages(bucket: dict[str, Any]) -> list[str]:
    available = [
        key
        for key in bucket
        if isinstance(key, str) and key.casefold() not in _NON_CAPTION_LANGUAGES
    ]
    preferred: list[str] = []
    for lang in _LANG_PREFERENCE:
        for key in available:
            if key.casefold() == lang and key not in preferred:
                preferred.append(key)
    for key in available:
        if key not in preferred:
            preferred.append(key)
    return preferred


def _pick_format(language: str, tracks: object) -> tuple[str, str, str] | None:
    if not isinstance(tracks, list):
        return None
    typed: list[dict[str, Any]] = [row for row in tracks if isinstance(row, dict)]
    for wanted in _FORMAT_PREFERENCE:
        for row in typed:
            ext = str(row.get("ext") or "")
            url = row.get("url")
            if ext.casefold() == wanted and isinstance(url, str) and url.startswith("https://"):
                return language, ext, url
    return None


def _looks_like_html(body: str) -> bool:
    start = body.lstrip()[:32].casefold()
    return start.startswith("<!doctype") or start.startswith("<html")


def _parse_json3(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    events = payload.get("events")
    if not isinstance(events, list):
        return ""
    pieces: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segs = event.get("segs")
        if not isinstance(segs, list):
            continue
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            utf8 = seg.get("utf8")
            if isinstance(utf8, str) and utf8.strip():
                pieces.append(utf8.strip())
    return " ".join(pieces).strip()


def _parse_vtt(body: str) -> str:
    pieces: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("WEBVTT") or stripped.startswith("NOTE"):
            continue
        if stripped.isdigit() or _VTT_TS.match(stripped):
            continue
        cleaned = _VTT_CUE.sub("", stripped).strip()
        if cleaned:
            pieces.append(cleaned)
    return " ".join(pieces).strip()


def _is_missing_captions(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".casefold()
    markers = ("no subtitle", "subtitles not", "requested format not available")
    return any(marker in text for marker in markers)
