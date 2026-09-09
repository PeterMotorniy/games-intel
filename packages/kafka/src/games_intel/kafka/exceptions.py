from __future__ import annotations


class GamesIntelError(Exception):
    """Base error for worker/daemon runtime."""


class TransientError(GamesIntelError):
    """Timeout, 429, 5xx, circuit_open — retry with backoff."""


class NotFoundError(GamesIntelError):
    """Expected business miss (e.g. game 404)."""


class ParseError(GamesIntelError):
    """Adapter could not parse a page; fail-closed."""


class SchemaError(GamesIntelError):
    """Invalid CloudEvent envelope or payload data."""


class QuotaError(GamesIntelError):
    """External API quota exhausted; degrade, do not retry."""


class LlmStructureError(GamesIntelError):
    """LLM structured output invalid after retry.llm_structure_retries."""
