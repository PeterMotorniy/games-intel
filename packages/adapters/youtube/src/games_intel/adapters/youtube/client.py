from __future__ import annotations

import asyncio
import logging

from games_intel.adapters.youtube.audio import AudioDownloader, YtDlpAudioDownloader
from games_intel.adapters.youtube.captions import CaptionsFetcher, YtDlpCaptionsFetcher
from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.filters import filter_and_sort_letsplays
from games_intel.adapters.youtube.ids import is_safe_video_id
from games_intel.adapters.youtube.search import VideoSearch, YtDlpVideoSearch
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


class YouTubeAdapter:
    """yt-dlp InnerTube search, captions, and audio. Timeout on every call. No STT."""

    def __init__(
        self,
        settings: Settings,
        *,
        search: VideoSearch | None = None,
        captions: CaptionsFetcher | None = None,
        audio: AudioDownloader | None = None,
    ) -> None:
        youtube = settings.adapters.youtube
        self._youtube = youtube
        self._timeout_seconds = youtube.timeout_seconds
        self._search = search if search is not None else YtDlpVideoSearch(self._timeout_seconds)
        self._captions = (
            captions if captions is not None else YtDlpCaptionsFetcher(self._timeout_seconds)
        )
        self._audio = audio if audio is not None else YtDlpAudioDownloader(self._timeout_seconds)

    async def aclose(self) -> None:
        return

    async def search_letsplays(self, inp: SearchLetsPlaysInput) -> LetsPlaySearch:
        query = _format_query(self._youtube.search_query_template, inp.title)
        hits = await self._call_search(query, inp.max_results)
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
                timeout=_media_timeout(self._timeout_seconds),
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
            audio_timeout = _media_timeout(self._timeout_seconds, inp.max_duration_seconds)
            audio_ref = await asyncio.wait_for(
                asyncio.to_thread(self._audio.download, inp.video_id, inp.max_duration_seconds),
                timeout=audio_timeout,
            )
        except Exception:
            return AudioResult(status="unavailable", audio_ref=None)
        if not audio_ref:
            return AudioResult(status="unavailable", audio_ref=None)
        return AudioResult(status="ok", audio_ref=audio_ref)

    async def _call_search(self, query: str, max_results: int) -> list[VideoHit]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._search.search, query, max_results),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise YoutubeAdapterError("timeout", "youtube search timed out") from exc
        except YoutubeAdapterError:
            raise
        except Exception as exc:
            raise YoutubeAdapterError("unavailable", "youtube search failed") from exc


HttpYouTubeAdapter = YouTubeAdapter


def _format_query(template: str, title: str) -> str:
    try:
        return template.format(title=title)
    except (KeyError, IndexError, ValueError) as exc:
        raise YoutubeAdapterError("unavailable", "invalid search_query_template") from exc


def _clip_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _media_timeout(base_seconds: int, extra_seconds: int = 0) -> float:
    """Captions/audio extract the player; 30s search timeout is too tight."""
    return float(max(base_seconds * 3, extra_seconds + 30, 90))
