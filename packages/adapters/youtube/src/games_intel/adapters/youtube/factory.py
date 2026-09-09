from __future__ import annotations

import httpx

from games_intel.adapters.youtube.audio import AudioDownloader
from games_intel.adapters.youtube.captions import CaptionsFetcher
from games_intel.adapters.youtube.client import HttpYouTubeAdapter
from games_intel.adapters.youtube.port import YouTubePort
from games_intel.settings import Settings


def create_youtube_port(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
    captions: CaptionsFetcher | None = None,
    audio: AudioDownloader | None = None,
) -> YouTubePort:
    return HttpYouTubeAdapter(settings, client=client, captions=captions, audio=audio)
