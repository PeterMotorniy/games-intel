from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from games_intel.agents.review_summarizer.checkpoint import (
    AGENT_NAME,
    build_thread_id,
    input_digest,
    open_checkpointer,
)
from games_intel.agents.review_summarizer.exceptions import LlmStructureError, LlmTransientError
from games_intel.agents.review_summarizer.graph import (
    ReviewSummarizerState,
    compile_review_summarizer_graph,
)
from games_intel.agents.review_summarizer.llm import (
    StructuredChatModel,
    build_chat_model,
    should_retry_llm,
)
from games_intel.agents.review_summarizer.prompt import load_prompt_template
from games_intel.agents.review_summarizer.tracing import (
    CallbacksFactory,
    build_tracing_callbacks,
    safe_callbacks,
)
from games_intel.contracts.agents import ReviewSummarizerInput, ReviewSummarizerOutput
from games_intel.contracts.payloads import ReviewSummary
from games_intel.settings import Settings

CloseFn = Callable[[], Awaitable[None]]


class ReviewSummarizer:
    """LangGraph ReviewSummarizerAgent: structured likes/dislikes/summary × 2."""

    def __init__(
        self,
        settings: Settings,
        *,
        model: StructuredChatModel,
        checkpointer: Any | None = None,
        callbacks_factory: CallbacksFactory | None = None,
        retry_fast: bool = False,
    ) -> None:
        self.settings = settings
        self._model = model
        self._system_prompt = load_prompt_template(settings.prompts.review_summarizer_path)
        self._injected_checkpointer = checkpointer
        self._checkpointer: Any | None = checkpointer
        self._close_checkpointer: CloseFn | None = None
        self._callbacks_factory: CallbacksFactory = (
            callbacks_factory
            if callbacks_factory is not None
            else lambda: build_tracing_callbacks(settings)
        )
        self._retry_fast = retry_fast
        self._graph: Any | None = None
        if checkpointer is not None:
            self._graph = self._compile(checkpointer)

    @property
    def graph(self) -> Any:
        if self._graph is None:
            msg = "graph is not compiled yet; call ainvoke first"
            raise RuntimeError(msg)
        return self._graph

    async def ainvoke(self, inp: ReviewSummarizerInput) -> ReviewSummarizerOutput:
        digest = input_digest(
            *(item.excerpt for item in inp.critic),
            *(item.excerpt for item in inp.user),
        )
        thread_id = build_thread_id(inp.run_id, inp.metacritic_slug, digest)
        graph = await self._ensure_graph()
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": safe_callbacks(self._callbacks_factory),
            "metadata": {
                "run_id": str(inp.run_id),
                "slug": inp.metacritic_slug,
                "agent": AGENT_NAME,
            },
            "run_name": AGENT_NAME,
        }
        cached = await self._completed_output(graph, config)
        if cached is not None:
            return cached
        try:
            result = await graph.ainvoke(_state_from_input(inp), config)
        except Exception as exc:
            mapped = _map_llm_failure(exc)
            if mapped is exc:
                raise
            raise mapped from exc
        return _output_from_state(result)

    async def aclose(self) -> None:
        if self._close_checkpointer is not None:
            await self._close_checkpointer()
            self._close_checkpointer = None

    async def _ensure_graph(self) -> Any:
        if self._graph is not None:
            return self._graph
        if self._injected_checkpointer is not None:
            self._checkpointer = self._injected_checkpointer
        else:
            self._checkpointer, self._close_checkpointer = await open_checkpointer(self.settings)
        self._graph = self._compile(self._checkpointer)
        return self._graph

    def _compile(self, checkpointer: Any) -> Any:
        return compile_review_summarizer_graph(
            model=self._model,
            system_prompt=self._system_prompt,
            settings=self.settings,
            checkpointer=checkpointer,
            retry_fast=self._retry_fast,
        )

    async def _completed_output(
        self, graph: Any, config: dict[str, Any]
    ) -> ReviewSummarizerOutput | None:
        snapshot = await graph.aget_state(config)
        values = getattr(snapshot, "values", None)
        nxt = getattr(snapshot, "next", ())
        if not values or nxt:
            return None
        critic = values.get("critic")
        user = values.get("user")
        if not critic or not user:
            return None
        return ReviewSummarizerOutput(
            critic=ReviewSummary.model_validate(critic),
            user=ReviewSummary.model_validate(user),
        )


def _state_from_input(inp: ReviewSummarizerInput) -> ReviewSummarizerState:
    return {
        "run_id": str(inp.run_id),
        "metacritic_slug": inp.metacritic_slug,
        "critic_snippets": [item.model_dump(mode="json") for item in inp.critic],
        "user_snippets": [item.model_dump(mode="json") for item in inp.user],
    }


def _output_from_state(state: dict[str, Any]) -> ReviewSummarizerOutput:
    return ReviewSummarizerOutput(
        critic=ReviewSummary.model_validate(state["critic"]),
        user=ReviewSummary.model_validate(state["user"]),
    )


def _unwrap_exception(exc: BaseException) -> Exception:
    if isinstance(exc, BaseExceptionGroup):
        preferred: Exception | None = None
        for inner in exc.exceptions:
            item = _unwrap_exception(inner)
            if isinstance(item, ValidationError | OutputParserException):
                return item
            if preferred is None:
                preferred = item
        if preferred is not None:
            return preferred
    if isinstance(exc, Exception):
        return exc
    raise exc


def _map_llm_failure(exc: Exception) -> Exception:
    err = _unwrap_exception(exc)
    if isinstance(err, ValidationError | OutputParserException):
        return LlmStructureError("structured output invalid after retries")
    if should_retry_llm(err):
        return LlmTransientError("model provider failed after retries")
    return err


def create_review_summarizer_agent(
    settings: Settings,
    *,
    model: StructuredChatModel | None = None,
    checkpointer: Any | None = None,
    callbacks_factory: CallbacksFactory | None = None,
    retry_fast: bool = False,
) -> ReviewSummarizer:
    resolved = model if model is not None else build_chat_model(settings)
    return ReviewSummarizer(
        settings,
        model=resolved,
        checkpointer=checkpointer,
        callbacks_factory=callbacks_factory,
        retry_fast=retry_fast,
    )
