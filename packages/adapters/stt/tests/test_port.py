from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from games_intel.adapters.stt.disabled import DisabledSttPort
from games_intel.adapters.stt.exceptions import SttAdapterError
from games_intel.adapters.stt.factory import create_stt_port
from games_intel.adapters.stt.fake import FakeSttPort
from games_intel.adapters.stt.files import read_audio_bytes
from games_intel.adapters.stt.timeout import TimeoutSttPort
from games_intel.adapters.stt.whisper import OpenAiWhisperStt
from games_intel.contracts.adapters import TranscribeInput
from games_intel.settings import Settings


def _settings(**stt_updates: object) -> Settings:
    base = Settings()
    stt = base.stt.model_copy(update=stt_updates)
    return base.model_copy(update={"stt": stt})


def test_read_audio_bytes_rejects_path_outside_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"RIFF" + b"\x00" * 12)
    nested = tmp_path / "tmp-root"
    nested.mkdir()
    monkeypatch.setattr("games_intel.adapters.stt.files.tempfile.gettempdir", lambda: str(nested))
    with pytest.raises(SttAdapterError) as exc:
        read_audio_bytes(str(outside))
    assert exc.value.code == "not_found"


async def test_fake_provider_returns_text() -> None:
    port = FakeSttPort(text="blogger narration", language="en")
    result = await port.transcribe(TranscribeInput(audio_ref="/tmp/clip.wav"))
    assert result.text == "blogger narration"
    assert result.language == "en"
    assert len(port.calls) == 1


async def test_timeout_is_enforced() -> None:
    inner = FakeSttPort(delay_seconds=1)
    port = TimeoutSttPort(inner, timeout_seconds=0.05)
    with pytest.raises(SttAdapterError) as exc:
        await port.transcribe(TranscribeInput(audio_ref="/tmp/clip.wav"))
    assert exc.value.code == "timeout"


async def test_disabled_port_raises_unavailable() -> None:
    port = DisabledSttPort()
    with pytest.raises(SttAdapterError) as exc:
        await port.transcribe(TranscribeInput(audio_ref="/tmp/clip.wav"))
    assert exc.value.code == "unavailable"
    assert "disabled" in exc.value.message


def test_factory_disabled_does_not_transcribe_until_enabled() -> None:
    settings = _settings(enabled=False)
    port = create_stt_port(settings)
    assert isinstance(port, TimeoutSttPort)


async def test_factory_disabled_does_not_transcribe() -> None:
    settings = _settings(enabled=False)
    port = create_stt_port(settings)
    with pytest.raises(SttAdapterError) as exc:
        await port.transcribe(TranscribeInput(audio_ref="/tmp/clip.wav"))
    assert "disabled" in exc.value.message


def test_factory_enabled_uses_openai_whisper() -> None:
    settings = _settings(enabled=True)
    port = create_stt_port(settings)
    assert isinstance(port, TimeoutSttPort)
    assert isinstance(port._inner, OpenAiWhisperStt)


async def test_openai_whisper_transcribes_without_network() -> None:
    audio = Path(tempfile.gettempdir()) / "gi-stt-test.wav"
    audio.write_bytes(b"RIFF" + b"\x00" * 12)
    settings = _settings(enabled=True, api_key=SecretStr("test-key"), model="whisper-1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/audio/translations")
        assert request.headers.get("authorization") == "Bearer test-key"
        return httpx.Response(200, json={"text": "hello from clip", "language": "en"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://api.openai.com/v1")
    try:
        port = OpenAiWhisperStt(settings, client=client)
        result = await port.transcribe(TranscribeInput(audio_ref=str(audio)))
    finally:
        audio.unlink(missing_ok=True)
    assert result.text == "hello from clip"
    assert result.language == "en"


async def test_openai_whisper_requires_api_key() -> None:
    settings = _settings(enabled=True, api_key=SecretStr(""))
    port = OpenAiWhisperStt(settings, client=httpx.AsyncClient())
    with pytest.raises(SttAdapterError) as exc:
        await port.transcribe(TranscribeInput(audio_ref="/tmp/a.wav"))
    assert exc.value.code == "unavailable"


async def test_factory_injects_fake_inner() -> None:
    fake = FakeSttPort(text="injected")
    port = create_stt_port(Settings(), inner=fake)
    result = await port.transcribe(TranscribeInput(audio_ref="/tmp/a.wav"))
    assert result.text == "injected"
