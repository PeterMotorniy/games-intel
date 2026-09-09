from __future__ import annotations

from games_intel.adapters.stt.exceptions import SttAdapterError
from games_intel.contracts.adapters import TranscribeInput, TranscribeResult


class DisabledSttPort:
    """Used when stt.enabled is false. Worker must not call transcribe."""

    async def transcribe(self, inp: TranscribeInput) -> TranscribeResult:
        raise SttAdapterError("unavailable", "stt is disabled")
