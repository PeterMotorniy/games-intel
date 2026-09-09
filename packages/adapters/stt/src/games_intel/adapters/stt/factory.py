from __future__ import annotations

from games_intel.adapters.stt.disabled import DisabledSttPort
from games_intel.adapters.stt.port import SttPort
from games_intel.adapters.stt.timeout import TimeoutSttPort
from games_intel.adapters.stt.whisper import OpenAiWhisperStt
from games_intel.settings import Settings


def create_stt_port(
    settings: Settings,
    *,
    inner: SttPort | None = None,
) -> SttPort:
    """Build OpenAI Whisper SttPort, or DisabledSttPort when STT is off."""

    wrapped = inner if inner is not None else _build_provider(settings)
    return TimeoutSttPort(wrapped, settings.stt.timeout_seconds)


def _build_provider(settings: Settings) -> SttPort:
    if not settings.stt.enabled:
        return DisabledSttPort()
    return OpenAiWhisperStt(settings)
