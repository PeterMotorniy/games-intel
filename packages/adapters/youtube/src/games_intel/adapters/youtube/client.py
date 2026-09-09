from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import HttpUrl, ValidationError

from games_intel.adapters.youtube.audio import AudioDownloader, YtDlpAudioDownloader
from games_intel.adapters.youtube.captions import CaptionsFetcher, YoutubeTranscriptFetcher
from games_intel.adapters.youtube.duration import parse_iso8601_duration
from games_intel.adapters.youtube.errors import map_youtube_http_error
from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.filters import filter_and_sort_letsplays
from games_intel.adapters.youtube.ids import is_safe_video_id
from games_intel.contracts.adapters import (
    AudioResult,
    GetAudioInput,
    GetTranscriptInput,
    LetsPlaySearch,
    SearchLetsPlaysInput,
    TranscriptResult,
    VideoHit,
)
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.adapters.youtube")

_API_BASE = "https://www.googleapis.com/youtube/v3"
_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
_SEARCH_MAX = 50


class HttpYouTubeAdapter:
    """YouTube Data API v3 search + timedtext captions. Timeout on every call. No STT."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        captions: CaptionsFetcher | None = None,
        audio: AudioDownloader | None = None,
    ) -> None:
        youtube = settings.adapters.youtube
        timeout = httpx.Timeout(youtube.timeout_seconds)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=_API_BASE, timeout=timeout)
        self._youtube = youtube
        self._api_key = youtube.api_key.get_secret_value()
        self._timeout_seconds = youtube.timeout_seconds
        self._captions = captions if captions is not None else YoutubeTranscriptFetcher()
        self._audio = audio if audio is not None else YtDlpAudioDownloader()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_letsplays(self, inp: SearchLetsPlaysInput) -> LetsPlaySearch:
        if not self._api_key:
            raise YoutubeAdapterError("unavailable", "youtube api_key is not configured")
        query = _format_query(self._youtube.search_query_template, inp.title)
        video_ids = await self._search_video_ids(query, inp.max_results)
        if not video_ids:
            return LetsPlaySearch(items=[])
        hits = await self._load_video_hits(video_ids)
        selected = filter_and_sort_letsplays(hits, inp.title, self._youtube)
        logger.info(
            "youtube search query_len=%s fetched=%s selected=%s",
            len(query),
            len(hits),
            len(selected),
        )
        return LetsPlaySearch(items=selected)

    async def get_transcript(self, inp: GetTranscriptInput) -> TranscriptResult:
        if not is_safe_video_id(inp.video_id):
            return TranscriptResult(
                status="transcript_unavailable", language=None, text="", truncated=False
            )
        try:
            fetched = await asyncio.wait_for(
                asyncio.to_thread(self._captions.fetch, inp.video_id),
                timeout=self._timeout_seconds,
            )
        except Exception:
            return TranscriptResult(
                status="transcript_unavailable", language=None, text="", truncated=False
            )
        if fetched is None or not fetched.text.strip():
            return TranscriptResult(
                status="transcript_unavailable", language=None, text="", truncated=False
            )
        text, truncated = _clip_text(fetched.text, inp.max_chars)
        return TranscriptResult(
            status="ok",
            language=fetched.language,
            text=text,
            truncated=truncated,
        )

    async def get_audio(self, inp: GetAudioInput) -> AudioResult:
        if not is_safe_video_id(inp.video_id):
            return AudioResult(status="unavailable", audio_ref=None)
        try:
            audio_timeout = max(self._timeout_seconds, inp.max_duration_seconds + 30)
            audio_ref = await asyncio.wait_for(
                asyncio.to_thread(self._audio.download, inp.video_id, inp.max_duration_seconds),
                timeout=audio_timeout,
            )
        except Exception:
            return AudioResult(status="unavailable", audio_ref=None)
        if not audio_ref:
            return AudioResult(status="unavailable", audio_ref=None)
        return AudioResult(status="ok", audio_ref=audio_ref)

    async def _search_video_ids(self, query: str, max_results: int) -> list[str]:
        params: dict[str, str | int] = {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": min(_SEARCH_MAX, max(max_results, 1)),
            "key": self._api_key,
        }
        payload = await self._get("/search", params)
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        video_ids: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id")
            if not isinstance(identifier, dict):
                continue
            video_id = identifier.get("videoId")
            if isinstance(video_id, str) and is_safe_video_id(video_id):
                video_ids.append(video_id)
        return video_ids

    async def _load_video_hits(self, video_ids: list[str]) -> list[VideoHit]:
        params: dict[str, str | int] = {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(video_ids),
            "key": self._api_key,
        }
        payload = await self._get("/videos", params)
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        hits: list[VideoHit] = []
        for item in items:
            hit = _video_hit_from_api(item)
            if hit is not None:
                hits.append(hit)
        return hits

    async def _get(self, path: str, params: Mapping[str, str | int]) -> dict[str, Any]:
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise YoutubeAdapterError("timeout", "youtube request timed out") from exc
        except httpx.HTTPError as exc:
            raise YoutubeAdapterError("unavailable", "youtube API unavailable") from exc
        if response.status_code != 200:
            body: object
            try:
                body = response.json()
            except ValueError:
                body = None
            raise map_youtube_http_error(response.status_code, body)
        try:
            payload = response.json()
        except ValueError as exc:
            raise YoutubeAdapterError("parse_error", "youtube response is not JSON") from exc
        if not isinstance(payload, dict):
            raise YoutubeAdapterError("parse_error", "youtube response must be an object")
        return payload


def _format_query(template: str, title: str) -> str:
    try:
        return template.format(title=title)
    except (KeyError, IndexError, ValueError) as exc:
        raise YoutubeAdapterError("unavailable", "invalid search_query_template") from exc


def _clip_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _video_hit_from_api(item: object) -> VideoHit | None:
    if not isinstance(item, dict):
        return None
    video_id = item.get("id")
    if not isinstance(video_id, str) or not video_id:
        return None
    snippet = item.get("snippet")
    details = item.get("contentDetails")
    stats = item.get("statistics")
    if not isinstance(snippet, dict) or not isinstance(details, dict):
        return None
    title = snippet.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    raw_duration = details.get("duration")
    if not isinstance(raw_duration, str):
        return None
    duration = parse_iso8601_duration(raw_duration)
    if duration is None:
        return None
    view_count = 0
    if isinstance(stats, dict):
        raw_views = stats.get("viewCount")
        if isinstance(raw_views, int):
            view_count = raw_views
        elif isinstance(raw_views, str) and raw_views.isdigit():
            view_count = int(raw_views)
    channel = snippet.get("channelTitle")
    channel_title = channel if isinstance(channel, str) and channel else None
    try:
        return VideoHit(
            video_id=video_id,
            title=title,
            view_count=view_count,
            duration_seconds=duration,
            channel_title=channel_title,
            url=HttpUrl(_WATCH_URL.format(video_id=video_id)),
        )
    except ValidationError:
        return None
