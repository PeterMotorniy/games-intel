from __future__ import annotations

from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.fake import FakeYouTubeAdapter
from games_intel.contracts.adapters import GetAudioInput, GetTranscriptInput, SearchLetsPlaysInput


async def test_fake_empty_search_is_valid() -> None:
    port = FakeYouTubeAdapter()
    result = await port.search_letsplays(SearchLetsPlaysInput(title="Elden Ring", max_results=10))
    assert result.items == []


async def test_fake_quota_error() -> None:
    port = FakeYouTubeAdapter(
        search_error=YoutubeAdapterError("quota_exceeded", "youtube quota exceeded")
    )
    try:
        await port.search_letsplays(SearchLetsPlaysInput(title="Elden Ring", max_results=10))
    except YoutubeAdapterError as exc:
        assert exc.code == "quota_exceeded"
    else:
        raise AssertionError("expected quota")


async def test_fake_tracks_audio_not_called_until_asked() -> None:
    port = FakeYouTubeAdapter()
    await port.get_transcript(GetTranscriptInput(video_id="abc", max_chars=100))
    assert port.audio_calls == []
    await port.get_audio(GetAudioInput(video_id="abc", max_duration_seconds=60))
    assert len(port.audio_calls) == 1
