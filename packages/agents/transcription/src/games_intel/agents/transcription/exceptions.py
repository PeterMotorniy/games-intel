from __future__ import annotations


class AgentError(Exception):
    """Base error for LLM/STT agents."""


class SttFailedError(AgentError):
    """STT provider failed after agent retries; worker degrades the stage."""
