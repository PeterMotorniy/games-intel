from __future__ import annotations

from typing import Protocol

from games_intel.contracts.adapters import TranscribeInput, TranscribeResult


class SttPort(Protocol):
    """audio_ref → text. Called from TranscriptionAgent, not from YouTubePort."""

    async def transcribe(self, inp: TranscribeInput) -> TranscribeResult: ...
