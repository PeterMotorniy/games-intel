from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from games_intel.agents.review_summarizer.llm import (
    STRUCTURED_OUTPUT_METHOD,
    StructuredChatModel,
    coerce_review_summary,
    should_retry_llm,
)
from games_intel.agents.review_summarizer.prompt import human_data_message
from games_intel.contracts.adapters import ReviewSnippet
from games_intel.contracts.payloads import ReviewSummary
from games_intel.settings import Settings


class ReviewSummarizerState(TypedDict, total=False):
    run_id: str
    metacritic_slug: str
    critic_snippets: list[dict[str, Any]]
    user_snippets: list[dict[str, Any]]
    critic: dict[str, Any]
    user: dict[str, Any]


def llm_retry_policy(settings: Settings, *, fast: bool = False) -> RetryPolicy:
    extra = settings.retry.llm_structure_retries
    return RetryPolicy(
        initial_interval=0 if fast else settings.retry.backoff_base_seconds,
        backoff_factor=1.0 if fast else 2.0,
        max_interval=0.01 if fast else settings.retry.backoff_max_seconds,
        max_attempts=1 + extra,
        jitter=False if fast else settings.retry.jitter_ratio > 0,
        retry_on=should_retry_llm,
    )


def compile_review_summarizer_graph(
    *,
    model: StructuredChatModel,
    system_prompt: str,
    settings: Settings,
    checkpointer: Any,
    retry_fast: bool = False,
) -> Any:
    retry = llm_retry_policy(settings, fast=retry_fast)
    timeout = settings.llm.timeout_seconds

    async def summarize_critic(state: ReviewSummarizerState) -> dict[str, Any]:
        summary = await _invoke_structured(
            model,
            system_prompt,
            audience="critic",
            snippets=_snippets_from_state(state.get("critic_snippets", [])),
        )
        return {"critic": summary.model_dump()}

    async def summarize_user(state: ReviewSummarizerState) -> dict[str, Any]:
        summary = await _invoke_structured(
            model,
            system_prompt,
            audience="user",
            snippets=_snippets_from_state(state.get("user_snippets", [])),
        )
        return {"user": summary.model_dump()}

    builder = StateGraph(ReviewSummarizerState)
    builder.add_node(
        "summarize_critic",
        summarize_critic,
        retry_policy=retry,
        timeout=timeout,
    )
    builder.add_node(
        "summarize_user",
        summarize_user,
        retry_policy=retry,
        timeout=timeout,
    )
    builder.add_edge(START, "summarize_critic")
    builder.add_edge(START, "summarize_user")
    builder.add_edge("summarize_critic", END)
    builder.add_edge("summarize_user", END)
    return builder.compile(checkpointer=checkpointer)


async def _invoke_structured(
    model: StructuredChatModel,
    system_prompt: str,
    *,
    audience: str,
    snippets: list[ReviewSnippet],
) -> ReviewSummary:
    structured = model.with_structured_output(ReviewSummary, method=STRUCTURED_OUTPUT_METHOD)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_data_message(audience=audience, snippets=snippets)),
    ]
    return coerce_review_summary(await structured.ainvoke(messages))


def _snippets_from_state(raw: list[dict[str, Any]]) -> list[ReviewSnippet]:
    return [ReviewSnippet.model_validate(item) for item in raw]
