from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.exceptions import (
    ModelError,
    OutputParserException,
)
from langgraph.errors import NodeTimeoutError
from pydantic import ValidationError

from games_intel.agents.review_summarizer.exceptions import LlmStructureError
from games_intel.contracts.payloads import ReviewSummary
from games_intel.settings import Settings


class StructuredRunnable(Protocol):
    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any: ...


class StructuredChatModel(Protocol):
    def with_structured_output(self, schema: type[Any], **kwargs: Any) -> StructuredRunnable: ...


def should_retry_llm(exc: Exception) -> bool:
    """Retry only schema misses and transient model-provider failures."""
    if isinstance(exc, ValidationError | OutputParserException | NodeTimeoutError):
        return True
    if isinstance(exc, TimeoutError | asyncio.TimeoutError):
        return True
    if isinstance(exc, ModelError) and getattr(exc, "is_retryable", False):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and (status == 429 or status >= 500):
        return True
    name = type(exc).__name__.lower()
    return "timeout" in name or "ratelimit" in name or "rate_limit" in name


def coerce_review_summary(result: Any) -> ReviewSummary:
    if isinstance(result, ReviewSummary):
        return result
    return ReviewSummary.model_validate(result)


STRUCTURED_OUTPUT_METHOD = "json_schema"


def build_chat_model(settings: Settings) -> StructuredChatModel:
    from langchain_openai import ChatOpenAI

    llm = settings.llm
    api_key = llm.api_key.get_secret_value().strip()
    if not llm.model.strip() or not api_key:
        return UnconfiguredChatModel()
    kwargs: dict[str, Any] = {
        "model": llm.model,
        "api_key": api_key,
        "temperature": llm.temperature,
        "timeout": llm.timeout_seconds,
        "max_tokens": llm.max_tokens,
        "max_retries": 0,
    }
    base_url = llm.base_url.strip().rstrip("/")
    if base_url:
        kwargs["base_url"] = base_url
        if "openrouter.ai" in base_url:
            kwargs["default_headers"] = {
                "HTTP-Referer": "http://localhost:8080",
                "X-OpenRouter-Title": "games-intel",
            }
    return ChatOpenAI(**kwargs)


class UnconfiguredChatModel:
    """Process can start without llm.model/api_key; structured invoke fails closed."""

    def with_structured_output(self, schema: type[Any], **kwargs: Any) -> StructuredRunnable:
        class _Bound:
            async def ainvoke(self, input: Any, config: Any = None, **kw: Any) -> Any:
                raise LlmStructureError("llm.model or llm.api_key is not configured")

        return _Bound()


class FakeStructuredChatModel:
    """Test double: `with_structured_output` returns queued ReviewSummary or errors."""

    def __init__(
        self,
        *,
        critic: Sequence[Any],
        user: Sequence[Any],
    ) -> None:
        self._critic = list(critic)
        self._user = list(user)
        self.critic_calls = 0
        self.user_calls = 0
        self.messages: list[Any] = []

    def with_structured_output(self, schema: type[Any], **kwargs: Any) -> StructuredRunnable:
        parent = self

        class _Bound:
            async def ainvoke(self, input: Any, config: Any = None, **kw: Any) -> Any:
                parent.messages.append(input)
                text = _messages_text(input)
                if "audience=user" in text:
                    parent.user_calls += 1
                    item = parent._user.pop(0)
                else:
                    parent.critic_calls += 1
                    item = parent._critic.pop(0)
                if isinstance(item, BaseException):
                    raise item
                if isinstance(item, schema):
                    return item
                return schema.model_validate(item)

        return _Bound()


def _messages_text(messages: Any) -> str:
    if isinstance(messages, str):
        return messages
    parts: list[str] = []
    if isinstance(messages, list):
        for item in messages:
            content = getattr(item, "content", None)
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(item, dict) and "content" in item:
                parts.append(str(item["content"]))
            else:
                parts.append(str(item))
    return "\n".join(parts)
