from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from games_intel.adapters.stt.exceptions import SttAdapterError
from games_intel.adapters.stt.factory import create_stt_port
from games_intel.adapters.stt.port import SttPort
from games_intel.agents.transcription.checkpoint import build_thread_id
from games_intel.agents.transcription.exceptions import SttFailedError
from games_intel.agents.transcription.tracing import safe_tracing_span
from games_intel.contracts.adapters import TranscribeInput
from games_intel.contracts.agents import TranscriptionInput, TranscriptionOutput
from games_intel.settings import Settings

SleepFn = Callable[[float], Awaitable[None]]

_TRANSIENT_CODES = frozenset({"timeout", "rate_limited", "unavailable", "circuit_open"})


class Transcription:
    """SttPort wrapper. No YouTube, no LangGraph."""

    def __init__(
        self,
        settings: Settings,
        port: SttPort,
        *,
        retry_fast: bool = False,
        sleep: SleepFn | None = None,
    ) -> None:
        self.settings = settings
        self.port = port
        self._retry_fast = retry_fast
        self._sleep: SleepFn = sleep if sleep is not None else asyncio.sleep

    async def ainvoke(self, inp: TranscriptionInput) -> TranscriptionOutput:
        thread_id = build_thread_id(inp.run_id, inp.metacritic_slug)
        with safe_tracing_span(self.settings, thread_id=thread_id):
            result = await self._transcribe_with_retry(inp.audio_ref)
        return TranscriptionOutput(text=result.text, language=result.language)

    async def aclose(self) -> None:
        close = getattr(self.port, "aclose", None)
        if close is not None:
            await close()

    async def _transcribe_with_retry(self, audio_ref: str) -> TranscriptionOutput:
        attempts = max(1, self.settings.retry.max_attempts)
        last_error: SttAdapterError | None = None
        for attempt in range(1, attempts + 1):
            try:
                dto = await self.port.transcribe(TranscribeInput(audio_ref=audio_ref))
                return TranscriptionOutput(text=dto.text, language=dto.language)
            except SttAdapterError as exc:
                last_error = exc
                if exc.code not in _TRANSIENT_CODES or attempt >= attempts:
                    break
                delay = 0.0 if self._retry_fast else _backoff_seconds(attempt, self.settings)
                if delay > 0:
                    await self._sleep(delay)
        message = "stt failed after retries"
        if last_error is not None:
            message = last_error.message
        raise SttFailedError(message) from last_error


def _backoff_seconds(attempt: int, settings: Settings) -> float:
    retry = settings.retry
    n = max(attempt, 1)
    delay = retry.backoff_base_seconds * (2 ** (n - 1))
    return float(min(delay, retry.backoff_max_seconds))


def create_transcription_agent(
    settings: Settings,
    *,
    port: SttPort | None = None,
    retry_fast: bool = False,
    sleep: SleepFn | None = None,
) -> Transcription:
    resolved = port if port is not None else create_stt_port(settings)
    return Transcription(settings, resolved, retry_fast=retry_fast, sleep=sleep)
