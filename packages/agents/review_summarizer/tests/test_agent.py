from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from langchain_core.exceptions import ModelAPIError
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr, ValidationError

from games_intel.agents.review_summarizer.agent import create_review_summarizer_agent
from games_intel.agents.review_summarizer.checkpoint import (
    build_thread_id,
    open_checkpointer,
    postgres_dsn,
)
from games_intel.agents.review_summarizer.exceptions import LlmStructureError, LlmTransientError
from games_intel.agents.review_summarizer.graph import llm_retry_policy
from games_intel.agents.review_summarizer.llm import (
    FakeStructuredChatModel,
    UnconfiguredChatModel,
    build_chat_model,
    should_retry_llm,
)
from games_intel.agents.review_summarizer.tracing import build_tracing_callbacks
from games_intel.contracts.adapters import ReviewSnippet
from games_intel.contracts.agents import ReviewSummarizerInput
from games_intel.contracts.payloads import ReviewSummary
from games_intel.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[4]
AGENT_SRC = REPO_ROOT / "packages/agents/review_summarizer/src/games_intel/agents/review_summarizer"
RUN_ID = UUID("0191c0aa-7e3b-7000-8000-0000000000aa")
SLUG = "elden-ring"

_CRITIC = ReviewSummary(
    likes=["глубокий бой"],
    dislikes=["баги запуска"],
    summary="Критики хвалят бой, но ругают запуск.",
)
_USER = ReviewSummary(
    likes=["атмосфера"],
    dislikes=["высокая сложность"],
    summary="Игрокам нравится мир, сложность утомляет.",
)


class _Http500Error(Exception):
    status_code = 500


class _Http429Error(Exception):
    status_code = 429


def _settings() -> Settings:
    base = Settings()
    retry = base.retry.model_copy(
        update={"llm_structure_retries": 2, "backoff_base_seconds": 0, "jitter_ratio": 0}
    )
    return base.model_copy(update={"retry": retry})


def _input() -> ReviewSummarizerInput:
    return ReviewSummarizerInput(
        run_id=RUN_ID,
        metacritic_slug=SLUG,
        critic=[
            ReviewSnippet(
                author="IGN", score=90, excerpt="The combat is excellent and the world is vast."
            )
        ],
        user=[
            ReviewSnippet(
                author="player1", score=8, excerpt="Love the atmosphere, too hard sometimes."
            )
        ],
    )


def _agent(
    model: FakeStructuredChatModel,
    *,
    callbacks_factory: Any | None = None,
) -> Any:
    return create_review_summarizer_agent(
        _settings(),
        model=model,
        checkpointer=InMemorySaver(),
        callbacks_factory=callbacks_factory,
        retry_fast=True,
    )


def test_thread_id_format_and_limit() -> None:
    thread_id = build_thread_id(RUN_ID, SLUG)
    assert thread_id == f"{RUN_ID}:{SLUG}:review_summarizer"
    assert len(thread_id) < 255
    with pytest.raises(ValueError, match="thread_id"):
        build_thread_id(RUN_ID, "x" * 300)


@pytest.mark.asyncio
async def test_fixture_snippets_yield_valid_pydantic() -> None:
    model = FakeStructuredChatModel(critic=[_CRITIC], user=[_USER])
    agent = _agent(model)
    output = await agent.ainvoke(_input())
    assert output.critic == _CRITIC
    assert output.user == _USER
    assert model.critic_calls == 1
    assert model.user_calls == 1
    joined = "\n".join(str(item) for item in model.messages)
    assert "UNTRUSTED DATA" in joined
    assert "audience=critic" in joined
    assert "audience=user" in joined


@pytest.mark.asyncio
async def test_schema_fail_then_success() -> None:
    invalid = {"likes": "not-a-list", "dislikes": [], "summary": "нет"}
    model = FakeStructuredChatModel(critic=[invalid, _CRITIC], user=[_USER])
    agent = _agent(model)
    output = await agent.ainvoke(_input())
    assert output.critic == _CRITIC
    assert output.user == _USER
    assert model.critic_calls == 2


@pytest.mark.asyncio
async def test_schema_fail_exhausted_raises_structure_error() -> None:
    invalid = {"likes": "nope", "dislikes": [], "summary": "x"}
    model = FakeStructuredChatModel(
        critic=[invalid, invalid, invalid],
        user=[_USER],
    )
    agent = _agent(model)
    with pytest.raises(LlmStructureError):
        await agent.ainvoke(_input())


@pytest.mark.asyncio
async def test_checkpoint_resume_does_not_recall_llm() -> None:
    model = FakeStructuredChatModel(critic=[_CRITIC], user=[_USER])
    agent = _agent(model)
    first = await agent.ainvoke(_input())
    model._critic = [RuntimeError("llm billed twice")]
    model._user = [RuntimeError("llm billed twice")]
    second = await agent.ainvoke(_input())
    assert first == second
    assert model.critic_calls == 1
    assert model.user_calls == 1


@pytest.mark.asyncio
async def test_provider_5xx_then_success() -> None:
    model = FakeStructuredChatModel(
        critic=[_Http500Error("upstream"), _CRITIC],
        user=[_USER],
    )
    agent = _agent(model)
    output = await agent.ainvoke(_input())
    assert output.critic == _CRITIC
    assert output.user == _USER
    assert model.critic_calls == 2


@pytest.mark.asyncio
async def test_provider_5xx_exhausted_raises_transient() -> None:
    model = FakeStructuredChatModel(
        critic=[ModelAPIError("provider 502") for _ in range(3)],
        user=[_USER],
    )
    agent = _agent(model)
    with pytest.raises(LlmTransientError):
        await agent.ainvoke(_input())
    assert model.critic_calls == 3


@pytest.mark.asyncio
async def test_callbacks_factory_failure_does_not_fail_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeStructuredChatModel(critic=[_CRITIC], user=[_USER])
    warnings: list[str] = []

    def boom() -> list[object]:
        raise ConnectionError("callbacks down")

    def capture_warning(message: str, *args: object, **kwargs: object) -> None:
        warnings.append(str(message))

    monkeypatch.setattr(
        "games_intel.agents.review_summarizer.tracing.logger.warning",
        capture_warning,
    )
    agent = _agent(model, callbacks_factory=boom)
    output = await agent.ainvoke(_input())
    assert output.critic.summary
    assert any("tracing callbacks failed" in item.lower() for item in warnings)


def test_graph_has_no_tools() -> None:
    model = FakeStructuredChatModel(critic=[_CRITIC], user=[_USER])
    agent = _agent(model)
    node_names = set(agent.graph.nodes)
    assert "tools" not in node_names
    assert "tool_node" not in node_names
    assert "summarize_critic" in node_names
    assert "summarize_user" in node_names


def test_agent_source_has_no_kafka_or_site_commands() -> None:
    for path in AGENT_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "games_intel.kafka" not in node.module
                assert "games_intel.adapters.metacritic" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "kafka" not in alias.name
        text = path.read_text(encoding="utf-8")
        assert "metacritic.com" not in text
        assert "bind_tools" not in text


def test_invalid_review_summary_is_validation_error() -> None:
    with pytest.raises(ValidationError):
        ReviewSummary.model_validate({"likes": "x", "dislikes": [], "summary": ""})


def test_should_retry_llm_covers_schema_timeout_and_http() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ReviewSummary.model_validate({"likes": "x", "dislikes": [], "summary": ""})
    assert should_retry_llm(exc_info.value)
    assert should_retry_llm(_Http500Error("x"))
    assert should_retry_llm(_Http429Error("x"))
    assert should_retry_llm(ModelAPIError("5xx"))
    assert should_retry_llm(TimeoutError("late"))
    assert not should_retry_llm(ValueError("not llm"))


def test_retry_policy_uses_structure_retries() -> None:
    policy = llm_retry_policy(_settings(), fast=True)
    assert policy.max_attempts == 3
    assert policy.retry_on is should_retry_llm


def test_postgres_dsn_strips_sqlalchemy_driver() -> None:
    assert (
        postgres_dsn("postgresql+asyncpg://games@localhost/db") == "postgresql://games@localhost/db"
    )
    assert postgres_dsn("postgres://games@localhost/db") == "postgresql://games@localhost/db"


@pytest.mark.asyncio
async def test_open_checkpointer_without_database_is_memory() -> None:
    settings = _settings().model_copy(
        update={"database": _settings().database.model_copy(update={"url": SecretStr("")})}
    )
    saver, close = await open_checkpointer(settings)
    assert close is None
    assert isinstance(saver, InMemorySaver)


def test_build_tracing_callbacks_are_empty() -> None:
    assert build_tracing_callbacks(Settings()) == []


def test_build_chat_model_reads_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)
    settings = _settings().model_copy(
        update={
            "llm": _settings().llm.model_copy(
                update={
                    "model": "gpt-test",
                    "api_key": SecretStr("sk-test"),
                    "temperature": 0.2,
                    "timeout_seconds": 11,
                    "max_tokens": 321,
                    "base_url": "https://llm.local/v1",
                }
            )
        }
    )
    build_chat_model(settings)
    assert captured["model"] == "gpt-test"
    assert captured["api_key"] == "sk-test"
    assert captured["temperature"] == 0.2
    assert captured["timeout"] == 11
    assert captured["max_tokens"] == 321
    assert captured["base_url"] == "https://llm.local/v1"
    assert captured["max_retries"] == 0
    assert "default_headers" not in captured


def test_build_chat_model_sets_openrouter_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)
    settings = _settings().model_copy(
        update={
            "llm": _settings().llm.model_copy(
                update={
                    "model": "google/gemini-2.5-flash-lite",
                    "api_key": SecretStr("sk-or-test"),
                    "base_url": "https://openrouter.ai/api/v1",
                }
            )
        }
    )
    build_chat_model(settings)
    assert captured["default_headers"]["HTTP-Referer"] == "http://localhost:8080"
    assert captured["default_headers"]["X-OpenRouter-Title"] == "games-intel"


def test_build_chat_model_empty_model_boots_unconfigured() -> None:
    settings = _settings().model_copy(
        update={"llm": _settings().llm.model_copy(update={"model": ""})}
    )
    model = build_chat_model(settings)
    assert isinstance(model, UnconfiguredChatModel)
    create_review_summarizer_agent(settings)


def test_build_chat_model_empty_api_key_boots_unconfigured() -> None:
    settings = _settings().model_copy(
        update={"llm": _settings().llm.model_copy(update={"api_key": SecretStr("")})}
    )
    model = build_chat_model(settings)
    assert isinstance(model, UnconfiguredChatModel)


@pytest.mark.asyncio
async def test_unconfigured_chat_model_fails_closed() -> None:
    bound = UnconfiguredChatModel().with_structured_output(ReviewSummary)
    with pytest.raises(LlmStructureError, match="llm.model or llm.api_key is not configured"):
        await bound.ainvoke({})
    assert (
        should_retry_llm(LlmStructureError("llm.model or llm.api_key is not configured")) is False
    )
