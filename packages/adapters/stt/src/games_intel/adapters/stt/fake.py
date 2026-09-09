from __future__ import annotations

from collections.abc import Callable

from games_intel.adapters.stt.exceptions import SttAdapterError
from games_intel.contracts.adapters import TranscribeInput, TranscribeResult


class FakeSttPort:
    """Deterministic STT. No network, no model download."""

    def __init__(
        self,
        *,
        text: str = "fake transcript",
        language: str | None = "en",
        error: SttAdapterError | None = None,
        delay_seconds: float = 0,
        sleeper: Callable[[float], object] | None = None,
    ) -> None:
        self._text = text
        self._language = language
        self._error = error
        self._delay_seconds = delay_seconds
        self._sleeper = sleeper
        self.calls: list[TranscribeInput] = []

    async def transcribe(self, inp: TranscribeInput) -> TranscribeResult:
        self.calls.append(inp)
        if self._delay_seconds > 0:
            if self._sleeper is not None:
                self._sleeper(self._delay_seconds)
            else:
                import asyncio

                await asyncio.sleep(self._delay_seconds)
        if self._error is not None:
            raise self._error
        return TranscribeResult(text=self._text, language=self._language)
