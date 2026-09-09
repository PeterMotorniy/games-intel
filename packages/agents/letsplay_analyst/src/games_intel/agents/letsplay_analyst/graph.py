from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from games_intel.agents.letsplay_analyst.llm import (
    STRUCTURED_OUTPUT_METHOD,
    StructuredChatModel,
    coerce_conclusion,
    should_retry_llm,
)
from games_intel.agents.letsplay_analyst.prompt import human_data_message
from games_intel.contracts.agents import LetsPlayConclusion
from games_intel.settings import Settings


class LetsPlayAnalystState(TypedDict, total=False):
    run_id: str
    metacritic_slug: str
    video_title: str
    transcript_excerpt: str
    conclusion: str
    highlights: list[str]


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


def compile_letsplay_analyst_graph(
    *,
    model: StructuredChatModel,
    system_prompt: str,
    settings: Settings,
    checkpointer: Any,
    retry_fast: bool = False,
) -> Any:
    retry = llm_retry_policy(settings, fast=retry_fast)
    timeout = settings.llm.timeout_seconds

    async def analyze(state: LetsPlayAnalystState) -> dict[str, Any]:
        structured = model.with_structured_output(
            LetsPlayConclusion, method=STRUCTURED_OUTPUT_METHOD
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=human_data_message(
                    video_title=state.get("video_title", ""),
                    transcript_excerpt=state.get("transcript_excerpt", ""),
                )
            ),
        ]
        result = coerce_conclusion(await structured.ainvoke(messages))
        return {"conclusion": result.conclusion, "highlights": list(result.highlights)}

    builder = StateGraph(LetsPlayAnalystState)
    builder.add_node("analyze", analyze, retry_policy=retry, timeout=timeout)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    return builder.compile(checkpointer=checkpointer)
