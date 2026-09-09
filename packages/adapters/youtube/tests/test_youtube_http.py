from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from pydantic import SecretStr

from games_intel.adapters.youtube.audio import FakeAudioDownloader
from games_intel.adapters.youtube.captions import CaptionsText, FakeCaptionsFetcher
from games_intel.adapters.youtube.client import HttpYouTubeAdapter
from games_intel.adapters.youtube.errors import map_youtube_http_error
from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.contracts.adapters import GetAudioInput, GetTranscriptInput, SearchLetsPlaysInput
from games_intel.settings import Settings


def _settings(*, api_key: str = "test-youtube-key") -> Settings:
    base = Settings()
    youtube = base.adapters.youtube.model_copy(update={"api_key": SecretStr(api_key)})
    adapters = base.adapters.model_copy(update={"youtube": youtube})
    return base.model_copy(update={"adapters": adapters})


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://www.googleapis.com/youtube/v3",
    )


def _search_and_videos_handler(
    search_items: list[dict[str, Any]],
    videos: list[dict[str, Any]],
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "key=" in str(request.url)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"items": search_items})
        if request.url.path.endswith("/videos"):
            return httpx.Response(200, json={"items": videos})
        return httpx.Response(404, json={"error": {"message": "missing"}})

    return handler


async def test_search_filters_fixture_hits_without_network() -> None:
    search_items = [
        {"id": {"videoId": "comp"}},
        {"id": {"videoId": "teaser"}},
        {"id": {"videoId": "lp"}},
    ]
    videos = [
        {
            "id": "comp",
            "snippet": {"title": "Elden Ring Compilation", "channelTitle": "A"},
            "contentDetails": {"duration": "PT1H"},
            "statistics": {"viewCount": "99999999"},
        },
        {
            "id": "teaser",
            "snippet": {"title": "Elden Ring Let's Play teaser", "channelTitle": "B"},
            "contentDetails": {"duration": "PT1M"},
            "statistics": {"viewCount": "8000000"},
        },
        {
            "id": "lp",
            "snippet": {"title": "Elden Ring Let's Play", "channelTitle": "C"},
            "contentDetails": {"duration": "PT40M"},
            "statistics": {"viewCount": "12000"},
        },
    ]
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler(search_items, videos)),
        captions=FakeCaptionsFetcher(),
        audio=FakeAudioDownloader(),
    )
    result = await adapter.search_letsplays(
        SearchLetsPlaysInput(title="Elden Ring", max_results=10)
    )
    assert [item.video_id for item in result.items] == ["lp"]
    assert result.items[0].view_count == 12_000


async def test_empty_search_items_is_valid() -> None:
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler([], [])),
        captions=FakeCaptionsFetcher(),
        audio=FakeAudioDownloader(),
    )
    result = await adapter.search_letsplays(
        SearchLetsPlaysInput(title="Elden Ring", max_results=10)
    )
    assert result.items == []


async def test_quota_exceeded_maps_to_adapter_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": 403,
                    "message": (
                        "The request cannot be completed because you have exceeded your quota."
                    ),
                    "errors": [{"reason": "quotaExceeded", "domain": "youtube.quota"}],
                }
            },
        )

    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(handler),
        captions=FakeCaptionsFetcher(),
        audio=FakeAudioDownloader(),
    )
    try:
        await adapter.search_letsplays(SearchLetsPlaysInput(title="Elden Ring", max_results=10))
    except YoutubeAdapterError as exc:
        assert exc.code == "quota_exceeded"
        assert "test-youtube-key" not in exc.message
    else:
        raise AssertionError("expected quota_exceeded")


def test_quota_mapper_does_not_embed_secrets() -> None:
    error = map_youtube_http_error(
        403,
        {
            "error": {
                "message": "The request cannot be completed because you have exceeded your quota.",
                "errors": [{"reason": "quotaExceeded"}],
            }
        },
    )
    assert error.code == "quota_exceeded"
    assert "secret" not in error.message


def test_http_429_maps_to_quota_exceeded() -> None:
    error = map_youtube_http_error(429, {"error": {"message": "rateLimitExceeded"}})
    assert error.code == "quota_exceeded"
    assert "rate limited" in error.message
    assert "key" not in error.message


class _BoomCaptions:
    def fetch(self, video_id: str) -> CaptionsText | None:
        del video_id
        raise YoutubeAdapterError("unavailable", "youtube captions request failed")


async def test_transcript_backend_error_is_unavailable_not_raised() -> None:
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler([], [])),
        captions=_BoomCaptions(),
        audio=FakeAudioDownloader(),
    )
    result = await adapter.get_transcript(GetTranscriptInput(video_id="abc", max_chars=100))
    assert result.status == "transcript_unavailable"
    assert result.text == ""


async def test_transcript_unavailable_is_not_an_exception() -> None:
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler([], [])),
        captions=FakeCaptionsFetcher(),
        audio=FakeAudioDownloader(),
    )
    result = await adapter.get_transcript(GetTranscriptInput(video_id="missing", max_chars=100))
    assert result.status == "transcript_unavailable"
    assert result.text == ""
    assert result.truncated is False


async def test_transcript_ok_truncated() -> None:
    captions = FakeCaptionsFetcher(
        {"abc": CaptionsText(text="hello world from blogger", language="en")}
    )
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler([], [])),
        captions=captions,
        audio=FakeAudioDownloader(),
    )
    result = await adapter.get_transcript(GetTranscriptInput(video_id="abc", max_chars=5))
    assert result.status == "ok"
    assert result.text == "hello"
    assert result.truncated is True
    assert result.language == "en"
    assert captions.calls == ["abc"]


async def test_get_audio_unavailable_without_exception() -> None:
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler([], [])),
        captions=FakeCaptionsFetcher(),
        audio=FakeAudioDownloader(),
    )
    result = await adapter.get_audio(GetAudioInput(video_id="missing", max_duration_seconds=1800))
    assert result.status == "unavailable"
    assert result.audio_ref is None


async def test_get_audio_uses_injected_downloader() -> None:
    downloader = FakeAudioDownloader({"abc": "/tmp/gi-yt-abc.m4a"})
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler([], [])),
        captions=FakeCaptionsFetcher(),
        audio=downloader,
    )
    result = await adapter.get_audio(GetAudioInput(video_id="abc", max_duration_seconds=1800))
    assert result.status == "ok"
    assert result.audio_ref == "/tmp/gi-yt-abc.m4a"
    assert downloader.calls == [("abc", 1800)]


async def test_get_audio_rejects_unsafe_video_id() -> None:
    downloader = FakeAudioDownloader({"../etc/passwd": "/tmp/evil.m4a"})
    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(_search_and_videos_handler([], [])),
        captions=FakeCaptionsFetcher(),
        audio=downloader,
    )
    result = await adapter.get_audio(
        GetAudioInput(video_id="../etc/passwd", max_duration_seconds=1800)
    )
    assert result.status == "unavailable"
    assert downloader.calls == []


async def test_missing_api_key_does_not_leak_in_message() -> None:
    adapter = HttpYouTubeAdapter(
        _settings(api_key=""),
        client=_client(_search_and_videos_handler([], [])),
        captions=FakeCaptionsFetcher(),
        audio=FakeAudioDownloader(),
    )
    try:
        await adapter.search_letsplays(SearchLetsPlaysInput(title="Elden Ring", max_results=5))
    except YoutubeAdapterError as exc:
        assert exc.code == "unavailable"
        assert "test-youtube-key" not in exc.message
        assert "not configured" in exc.message
    else:
        raise AssertionError("expected missing key error")


async def test_timeout_maps_without_url() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    adapter = HttpYouTubeAdapter(
        _settings(),
        client=_client(handler),
        captions=FakeCaptionsFetcher(),
        audio=FakeAudioDownloader(),
    )
    try:
        await adapter.search_letsplays(SearchLetsPlaysInput(title="Elden Ring", max_results=5))
    except YoutubeAdapterError as exc:
        assert exc.code == "timeout"
        assert "test-youtube-key" not in str(exc)
    else:
        raise AssertionError("expected timeout")
