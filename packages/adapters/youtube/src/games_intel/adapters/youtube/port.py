from __future__ import annotations

from typing import Protocol

from games_intel.contracts.adapters import (
    AudioResult,
    GetAudioInput,
    GetTranscriptInput,
    LetsPlaySearch,
    SearchLetsPlaysInput,
    TranscriptResult,
)


class YouTubePort(Protocol):
    """In-process YouTube Data API + captions. Does not run STT."""

    async def search_letsplays(self, inp: SearchLetsPlaysInput) -> LetsPlaySearch: ...

    async def get_transcript(self, inp: GetTranscriptInput) -> TranscriptResult: ...

    async def get_audio(self, inp: GetAudioInput) -> AudioResult: ...
