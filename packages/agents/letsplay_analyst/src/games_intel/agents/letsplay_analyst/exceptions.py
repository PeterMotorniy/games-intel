from __future__ import annotations


class AgentError(Exception):
    """Base error for LLM/STT agents."""


class LlmStructureError(AgentError):
    """Structured output did not match the Pydantic schema after retries."""


class LlmTransientError(AgentError):
    """Timeout or 5xx from the model provider after agent retries."""
