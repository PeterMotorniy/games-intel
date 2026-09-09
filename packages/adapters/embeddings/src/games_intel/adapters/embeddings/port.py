from __future__ import annotations

from typing import Protocol

from games_intel.contracts.adapters import EmbedTextInput, EmbedTextResult


class EmbeddingPort(Protocol):
    """HTTP embedding API. Not a LangGraph agent."""

    async def embed(self, inp: EmbedTextInput) -> EmbedTextResult: ...
