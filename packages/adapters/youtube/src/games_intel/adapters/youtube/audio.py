from __future__ import annotations

import logging
import shutil
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.ids import is_safe_video_id, watch_url
from games_intel.adapters.youtube.ydl import ydl_options

logger = logging.getLogger("games_intel.adapters.youtube")


class AudioDownloader(Protocol):
    def download(
        self,
        video_id: str,
        max_duration_seconds: int,
        cancel: threading.Event | None = None,
    ) -> str | None: ...


class YtDlpAudioDownloader:
    """Clip audio to max_duration_seconds. Does not run STT."""

    def __init__(self, timeout_seconds: int = 30) -> None:
        self._timeout_seconds = timeout_seconds

    def download(
        self,
        video_id: str,
        max_duration_seconds: int,
        cancel: threading.Event | None = None,
    ) -> str | None:
        if not is_safe_video_id(video_id):
            logger.warning("youtube audio refused unsafe video_id")
            return None
        try:
            import yt_dlp
        except ImportError as exc:
            raise YoutubeAdapterError("unavailable", "youtube audio backend missing") from exc
        target_dir = Path(tempfile.mkdtemp(prefix="gi-yt-audio-"))
        outtmpl = str(target_dir / f"{video_id}.%(ext)s")
        end = max(1, max_duration_seconds)

        def _ranges(_info: object, _ydl: object) -> list[dict[str, float]]:
            return [{"start_time": 0.0, "end_time": float(end)}]

        def _progress(_status: object) -> None:
            if cancel is not None and cancel.is_set():
                raise YoutubeAdapterError("timeout", "audio download cancelled")

        options = ydl_options(
            self._timeout_seconds,
            format="bestaudio/best",
            outtmpl=outtmpl,
            download_ranges=_ranges,
            noplaylist=True,
            progress_hooks=[_progress],
        )
        url = watch_url(video_id)
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
        except Exception as exc:
            logger.warning(
                "youtube audio download failed video_id=%s error_type=%s",
                video_id,
                type(exc).__name__,
            )
            shutil.rmtree(target_dir, ignore_errors=True)
            return None
        files = [path for path in target_dir.iterdir() if path.is_file()]
        if not files:
            shutil.rmtree(target_dir, ignore_errors=True)
            return None
        return str(files[0])


class FakeAudioDownloader:
    def __init__(self, mapping: Mapping[str, str | None] | None = None) -> None:
        self._mapping = dict(mapping or {})
        self.calls: list[tuple[str, int]] = []

    def download(
        self,
        video_id: str,
        max_duration_seconds: int,
        cancel: threading.Event | None = None,
    ) -> str | None:
        del cancel
        self.calls.append((video_id, max_duration_seconds))
        if video_id not in self._mapping:
            return None
        return self._mapping[video_id]


def cleanup_downloaded_audio(audio_ref: str | None) -> None:
    """Remove yt-dlp temp clip and its directory. No-op for non-download paths."""
    if not audio_ref:
        return
    try:
        path = Path(audio_ref).expanduser().resolve()
    except OSError:
        return
    if not path.parent.name.startswith("gi-yt-audio-"):
        return
    try:
        if path.is_file():
            path.unlink()
        path.parent.rmdir()
    except OSError:
        return
