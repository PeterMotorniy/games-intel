from __future__ import annotations

from collections.abc import Mapping, Sequence

from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.contracts.adapters import (
    AudioResult,
    GetAudioInput,
    GetTranscriptInput,
    LetsPlaySearch,
    SearchLetsPlaysInput,
    TranscriptResult,
    VideoHit,
)


class FakeYouTubeAdapter:
    """In-process YouTubePort. No network. Worker tests inject already-ranked hits."""

    def __init__(
        self,
        *,
        items: Sequence[VideoHit] | None = None,
        transcripts: Mapping[str, TranscriptResult] | None = None,
        audio: Mapping[str, AudioResult] | None = None,
        search_error: YoutubeAdapterError | None = None,
        transcript_errors: Mapping[str, YoutubeAdapterError] | None = None,
        audio_errors: Mapping[str, YoutubeAdapterError] | None = None,
    ) -> None:
        self._items = list(items or [])
        self._transcripts = dict(transcripts or {})
        self._audio = dict(audio or {})
        self._search_error = search_error
        self._transcript_errors = dict(transcript_errors or {})
        self._audio_errors = dict(audio_errors or {})
        self.search_calls: list[SearchLetsPlaysInput] = []
        self.transcript_calls: list[GetTranscriptInput] = []
        self.audio_calls: list[GetAudioInput] = []

    async def search_letsplays(self, inp: SearchLetsPlaysInput) -> LetsPlaySearch:
        self.search_calls.append(inp)
        if self._search_error is not None:
            raise self._search_error
        return LetsPlaySearch(items=list(self._items))

    async def get_transcript(self, inp: GetTranscriptInput) -> TranscriptResult:
        self.transcript_calls.append(inp)
        error = self._transcript_errors.get(inp.video_id)
        if error is not None:
            raise error
        found = self._transcripts.get(inp.video_id)
        if found is not None:
            return found
        return TranscriptResult(
            status="transcript_unavailable", language=None, text="", truncated=False
        )

    async def get_audio(self, inp: GetAudioInput) -> AudioResult:
        self.audio_calls.append(inp)
        error = self._audio_errors.get(inp.video_id)
        if error is not None:
            raise error
        found = self._audio.get(inp.video_id)
        if found is not None:
            return found
        return AudioResult(status="unavailable", audio_ref=None)
