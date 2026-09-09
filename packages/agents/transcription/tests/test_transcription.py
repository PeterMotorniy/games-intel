from __future__ import annotations

import ast
from pathlib import Path
from uuid import UUID

import pytest

from games_intel.adapters.stt.exceptions import SttAdapterError
from games_intel.adapters.stt.fake import FakeSttPort
from games_intel.agents.transcription.agent import create_transcription_agent
from games_intel.agents.transcription.checkpoint import build_thread_id
from games_intel.agents.transcription.exceptions import SttFailedError
from games_intel.contracts.adapters import TranscribeInput, TranscribeResult
from games_intel.contracts.agents import TranscriptionInput
from games_intel.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[4]
AGENT_SRC = REPO_ROOT / "packages/agents/transcription/src/games_intel/agents/transcription"
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-0000000000aa")
SLUG = "elden-ring"


def _settings() -> Settings:
    base = Settings()
    retry = base.retry.model_copy(
        update={"max_attempts": 3, "backoff_base_seconds": 0, "jitter_ratio": 0}
    )
    return base.model_copy(update={"retry": retry})


def _input() -> TranscriptionInput:
    return TranscriptionInput(run_id=RUN_ID, metacritic_slug=SLUG, audio_ref="file://clip.wav")


def test_thread_id_format_and_limit() -> None:
    thread_id = build_thread_id(RUN_ID, SLUG)
    assert thread_id == f"{RUN_ID}:{SLUG}:transcription"
    assert len(thread_id) < 255
    with pytest.raises(ValueError, match="thread_id"):
        build_thread_id(RUN_ID, "x" * 300)


@pytest.mark.asyncio
async def test_transcribe_uses_stt_port_only() -> None:
    port = FakeSttPort(text="hello from whisper", language="en")
    agent = create_transcription_agent(_settings(), port=port, retry_fast=True)
    output = await agent.ainvoke(_input())
    assert output.text == "hello from whisper"
    assert output.language == "en"
    assert len(port.calls) == 1
    assert port.calls[0].audio_ref == "file://clip.wav"


@pytest.mark.asyncio
async def test_transient_stt_fail_then_success() -> None:
    class _Flaky(FakeSttPort):
        def __init__(self) -> None:
            super().__init__(text="recovered")
            self.attempts = 0

        async def transcribe(self, inp: TranscribeInput) -> TranscribeResult:
            self.attempts += 1
            if self.attempts < 3:
                raise SttAdapterError("timeout", "stt timeout")
            return await super().transcribe(inp)

    port = _Flaky()
    agent = create_transcription_agent(_settings(), port=port, retry_fast=True)
    output = await agent.ainvoke(_input())
    assert output.text == "recovered"
    assert port.attempts == 3


@pytest.mark.asyncio
async def test_stt_fail_exhausted_raises_failed() -> None:
    port = FakeSttPort(error=SttAdapterError("timeout", "always down"))
    agent = create_transcription_agent(_settings(), port=port, retry_fast=True)
    with pytest.raises(SttFailedError):
        await agent.ainvoke(_input())
    assert len(port.calls) == 3


@pytest.mark.asyncio
async def test_tracing_span_failure_does_not_fail_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[str] = []

    def capture(message: str, *args: object, **kwargs: object) -> None:
        warnings.append(str(message))

    monkeypatch.setattr("games_intel.agents.transcription.tracing.logger.warning", capture)

    def boom(*args: object, **kwargs: object) -> object:
        raise ConnectionError("span down")

    monkeypatch.setattr(
        "games_intel.agents.transcription.tracing.tracing_span",
        boom,
    )
    port = FakeSttPort(text="ok")
    agent = create_transcription_agent(_settings(), port=port, retry_fast=True)
    output = await agent.ainvoke(_input())
    assert output.text == "ok"
    assert any("tracing span failed" in item.lower() for item in warnings)


def test_agent_source_has_no_youtube_or_kafka() -> None:
    for path in AGENT_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "games_intel.kafka" not in node.module
                assert "games_intel.adapters.youtube" not in node.module
                assert "langgraph" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "kafka" not in alias.name
                    assert "youtube" not in alias.name
        text = path.read_text(encoding="utf-8")
        assert "googleapis.com/youtube" not in text
        assert "search_letsplays" not in text
