from __future__ import annotations

from pydantic import HttpUrl

from games_intel.adapters.youtube.audio import FakeAudioDownloader
from games_intel.adapters.youtube.captions import CaptionsText, FakeCaptionsFetcher
from games_intel.adapters.youtube.client import YouTubeAdapter
from games_intel.adapters.youtube.errors import map_ytdlp_error
from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.search import FakeVideoSearch, hit_from_extractor_entry
from games_intel.contracts.adapters import (
    GetAudioInput,
    GetTranscriptInput,
    SearchLetsPlaysInput,
    VideoHit,
)
from games_intel.settings import Settings


def _settings() -> Settings:
    return Settings()


def _hit(
    video_id: str,
    title: str,
    *,
    views: int,
    duration: int,
) -> VideoHit:
    return VideoHit(
        video_id=video_id,
        title=title,
        view_count=views,
        duration_seconds=duration,
        channel_title="C",
        url=HttpUrl(f"https://www.youtube.com/watch?v={video_id}"),
    )


def _adapter(
    *,
    search: FakeVideoSearch | None = None,
    captions: FakeCaptionsFetcher | None = None,
    audio: FakeAudioDownloader | None = None,
) -> YouTubeAdapter:
    return YouTubeAdapter(
        _settings(),
        search=search if search is not None else FakeVideoSearch(),
        captions=captions if captions is not None else FakeCaptionsFetcher(),
        audio=audio if audio is not None else FakeAudioDownloader(),
    )


async def test_search_filters_fixture_hits_without_network() -> None:
    search = FakeVideoSearch(
        [
            _hit("comp", "Elden Ring Compilation", views=99_999_999, duration=3600),
            _hit("teaser", "Elden Ring Let's Play teaser", views=8_000_000, duration=60),
            _hit("lp", "Elden Ring Let's Play", views=12_000, duration=2400),
        ]
    )
    adapter = _adapter(search=search)
    result = await adapter.search_letsplays(
        SearchLetsPlaysInput(title="Elden Ring", max_results=10)
    )
    assert [item.video_id for item in result.items] == ["lp"]
    assert result.items[0].view_count == 12_000
    assert search.calls == [("Elden Ring let's play", 10)]


async def test_empty_search_items_is_valid() -> None:
    result = await _adapter().search_letsplays(
        SearchLetsPlaysInput(title="Elden Ring", max_results=10)
    )
    assert result.items == []


async def test_search_without_api_key() -> None:
    result = await _adapter().search_letsplays(
        SearchLetsPlaysInput(title="Elden Ring", max_results=5)
    )
    assert result.items == []


async def test_search_timeout_maps_without_payload() -> None:
    search = FakeVideoSearch(error=TimeoutError("slow"))
    adapter = _adapter(search=search)
    try:
        await adapter.search_letsplays(SearchLetsPlaysInput(title="Elden Ring", max_results=5))
    except YoutubeAdapterError as exc:
        assert exc.code == "timeout"
        assert "watch?v=" not in exc.message
    else:
        raise AssertionError("expected timeout")


async def test_search_rate_limit_maps_without_url() -> None:
    mapped = map_ytdlp_error(RuntimeError("HTTP Error 429: Too Many Requests https://youtube.com"))
    search = FakeVideoSearch(error=mapped)
    adapter = _adapter(search=search)
    try:
        await adapter.search_letsplays(SearchLetsPlaysInput(title="Elden Ring", max_results=5))
    except YoutubeAdapterError as exc:
        assert exc.code == "rate_limited"
        assert "youtube.com" not in exc.message
    else:
        raise AssertionError("expected rate_limited")


def test_ytdlp_mapper_does_not_embed_urls() -> None:
    error = map_ytdlp_error(
        RuntimeError("HTTP Error 429 https://youtube.com/watch?v=abc&key=secret")
    )
    assert error.code == "rate_limited"
    assert "secret" not in error.message
    assert "youtube.com" not in error.message


def test_hit_from_extractor_entry() -> None:
    hit = hit_from_extractor_entry(
        {
            "id": "lp",
            "title": "Elden Ring Let's Play",
            "duration": 2400,
            "view_count": "12000",
            "channel": "C",
        }
    )
    assert hit is not None
    assert hit.video_id == "lp"
    assert hit.view_count == 12_000
    assert hit.duration_seconds == 2400


class _BoomCaptions:
    def fetch(self, video_id: str) -> CaptionsText | None:
        del video_id
        raise YoutubeAdapterError("unavailable", "youtube captions request failed")


async def test_transcript_backend_error_is_unavailable_not_raised() -> None:
    result = await _adapter(captions=_BoomCaptions()).get_transcript(
        GetTranscriptInput(video_id="abc", max_chars=100)
    )
    assert result.status == "transcript_unavailable"
    assert result.text == ""


async def test_transcript_unavailable_is_not_an_exception() -> None:
    result = await _adapter().get_transcript(GetTranscriptInput(video_id="missing", max_chars=100))
    assert result.status == "transcript_unavailable"
    assert result.text == ""
    assert result.truncated is False


async def test_transcript_ok_truncated() -> None:
    captions = FakeCaptionsFetcher(
        {"abc": CaptionsText(text="hello world from blogger", language="en")}
    )
    result = await _adapter(captions=captions).get_transcript(
        GetTranscriptInput(video_id="abc", max_chars=5)
    )
    assert result.status == "ok"
    assert result.text == "hello"
    assert result.truncated is True
    assert result.language == "en"
    assert captions.calls == ["abc"]


async def test_get_audio_unavailable_without_exception() -> None:
    result = await _adapter().get_audio(
        GetAudioInput(video_id="missing", max_duration_seconds=1800)
    )
    assert result.status == "unavailable"
    assert result.audio_ref is None


async def test_get_audio_uses_injected_downloader() -> None:
    downloader = FakeAudioDownloader({"abc": "/tmp/gi-yt-abc.m4a"})
    result = await _adapter(audio=downloader).get_audio(
        GetAudioInput(video_id="abc", max_duration_seconds=1800)
    )
    assert result.status == "ok"
    assert result.audio_ref == "/tmp/gi-yt-abc.m4a"
    assert downloader.calls == [("abc", 1800)]


async def test_get_audio_rejects_unsafe_video_id() -> None:
    downloader = FakeAudioDownloader({"../etc/passwd": "/tmp/evil.m4a"})
    result = await _adapter(audio=downloader).get_audio(
        GetAudioInput(video_id="../etc/passwd", max_duration_seconds=1800)
    )
    assert result.status == "unavailable"
    assert downloader.calls == []
