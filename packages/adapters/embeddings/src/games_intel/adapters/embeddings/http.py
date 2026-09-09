from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError

from games_intel.adapters.embeddings.exceptions import EmbeddingAdapterError
from games_intel.contracts.adapters import AdapterErrorCode, EmbedTextInput, EmbedTextResult
from games_intel.settings import Settings

_STATUS_TO_CODE: dict[int, AdapterErrorCode] = {
    401: "unavailable",
    403: "unavailable",
    404: "unavailable",
    408: "timeout",
    429: "rate_limited",
    422: "parse_error",
    503: "unavailable",
    504: "timeout",
}


class HttpEmbeddingAdapter:
    """OpenAI-compatible embeddings client (`POST /v1/embeddings`). Timeout on every call."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        embeddings = settings.embeddings
        timeout = httpx.Timeout(settings.app.http_timeout_seconds)
        base_url = embeddings.base_url.strip().rstrip("/") or settings.llm.base_url.strip().rstrip(
            "/"
        )
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._model = embeddings.model
        self._vector_dim = embeddings.vector_dim
        self._api_key = (
            embeddings.api_key.get_secret_value().strip()
            or settings.llm.api_key.get_secret_value().strip()
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def embed(self, inp: EmbedTextInput) -> EmbedTextResult:
        if not self._api_key:
            raise EmbeddingAdapterError("unavailable", "openai api_key is not configured")
        payload = {
            "model": self._model,
            "input": inp.text,
            "dimensions": self._vector_dim,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = await self._client.post("/embeddings", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise EmbeddingAdapterError("timeout", "embedding request timed out") from exc
        except httpx.HTTPError as exc:
            raise EmbeddingAdapterError("unavailable", "embedding API unavailable") from exc
        if response.status_code != 200:
            code: AdapterErrorCode = _STATUS_TO_CODE.get(response.status_code, "unavailable")
            if response.status_code >= 500:
                code = "unavailable"
            raise EmbeddingAdapterError(code, f"embedding HTTP {response.status_code}")
        try:
            body: Any = response.json()
        except ValueError as exc:
            raise EmbeddingAdapterError("parse_error", "embedding response is not JSON") from exc
        vector = _parse_vector(body)
        if len(vector) != self._vector_dim:
            raise EmbeddingAdapterError(
                "parse_error",
                f"embedding dimension {len(vector)} != {self._vector_dim}",
            )
        try:
            return EmbedTextResult(vector=vector)
        except ValidationError as exc:
            raise EmbeddingAdapterError("parse_error", "invalid embedding vector") from exc


def _parse_vector(body: object) -> list[float]:
    if not isinstance(body, dict):
        raise EmbeddingAdapterError("parse_error", "embedding body must be an object")
    data = body.get("data")
    raw: object = None
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            raw = first.get("embedding")
    if raw is None:
        embeddings = body.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            raw = embeddings[0]
        else:
            raw = body.get("embedding")
    if not isinstance(raw, list) or not raw:
        raise EmbeddingAdapterError("parse_error", "embedding vector missing")
    try:
        return [float(item) for item in raw]
    except (TypeError, ValueError) as exc:
        raise EmbeddingAdapterError("parse_error", "embedding vector is not numeric") from exc
