from __future__ import annotations

import asyncio

from games_intel.adapters.stt.exceptions import SttAdapterError
from games_intel.adapters.stt.port import SttPort
from games_intel.contracts.adapters import TranscribeInput, TranscribeResult


class TimeoutSttPort:
    """Enforces stt.timeout_seconds around any provider."""

    def __init__(self, inner: SttPort, timeout_seconds: float) -> None:
        self._inner = inner
        self._timeout_seconds = timeout_seconds

    async def transcribe(self, inp: TranscribeInput) -> TranscribeResult:
        try:
            return await asyncio.wait_for(
                self._inner.transcribe(inp),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise SttAdapterError("timeout", "stt timed out") from exc
