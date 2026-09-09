from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence

from games_intel.contracts.adapters import EmbedTextInput, EmbedTextResult
from games_intel.settings import Settings


class FakeEmbeddingAdapter:
    """Deterministic in-process embeddings. No network. Tests inject vectors by substring."""

    def __init__(
        self,
        settings: Settings,
        *,
        vectors: Mapping[str, Sequence[float]] | None = None,
    ) -> None:
        self._dim = settings.embeddings.vector_dim
        self._vectors = dict(vectors or {})
        self.calls: list[str] = []

    async def embed(self, inp: EmbedTextInput) -> EmbedTextResult:
        self.calls.append(inp.text)
        for needle, vector in self._vectors.items():
            if needle and needle in inp.text:
                return EmbedTextResult(vector=_fit_dim(vector, self._dim))
        return EmbedTextResult(vector=_unit_from_text(inp.text, self._dim))


def _fit_dim(vector: Sequence[float], dim: int) -> list[float]:
    values = list(vector)
    if len(values) == dim:
        return values
    if len(values) > dim:
        return values[:dim]
    return values + [0.0] * (dim - len(values))


def _unit_from_text(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    seed = digest
    while len(values) < dim:
        for byte in seed:
            values.append((byte / 255.0) * 2.0 - 1.0)
            if len(values) >= dim:
                break
        seed = hashlib.sha256(seed).digest()
    norm = math.sqrt(sum(item * item for item in values))
    if norm == 0:
        values[0] = 1.0
        return values
    return [item / norm for item in values]
