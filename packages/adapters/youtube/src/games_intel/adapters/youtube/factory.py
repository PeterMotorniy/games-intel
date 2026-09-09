from __future__ import annotations

from games_intel.adapters.youtube.audio import AudioDownloader
from games_intel.adapters.youtube.captions import CaptionsFetcher
from games_intel.adapters.youtube.client import YouTubeAdapter
from games_intel.adapters.youtube.port import YouTubePort
from games_intel.adapters.youtube.search import VideoSearch
from games_intel.settings import Settings


def create_youtube_port(
    settings: Settings,
    *,
    search: VideoSearch | None = None,
    captions: CaptionsFetcher | None = None,
    audio: AudioDownloader | None = None,
) -> YouTubePort:
    return YouTubeAdapter(settings, search=search, captions=captions, audio=audio)
