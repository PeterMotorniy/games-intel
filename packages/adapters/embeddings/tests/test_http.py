from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from games_intel.adapters.embeddings.exceptions import EmbeddingAdapterError
from games_intel.adapters.embeddings.http import HttpEmbeddingAdapter
from games_intel.contracts.adapters import EmbedTextInput
from games_intel.settings import Settings


def _settings(*, dim: int = 4, api_key: str = "test-key") -> Settings:
    base = Settings()
    embeddings = base.embeddings.model_copy(
        update={
            "model": "text-embedding-3-small",
            "vector_dim": dim,
            "base_url": "https://embed.test",
            "api_key": SecretStr(api_key),
        }
    )
    return base.model_copy(update={"embeddings": embeddings})


async def test_http_embed_parses_vector_without_network() -> None:
    vector = [0.1, 0.2, 0.3, 0.4]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/embeddings")
        assert request.headers.get("authorization") == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "text-embedding-3-small"
        assert body["input"] == "title: Elden Ring"
        assert body["dimensions"] == 4
        return httpx.Response(200, json={"data": [{"embedding": vector, "index": 0}]})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://embed.test")
    adapter = HttpEmbeddingAdapter(_settings(), client=client)
    result = await adapter.embed(EmbedTextInput(text="title: Elden Ring"))
    assert result.vector == vector


async def test_http_embed_maps_timeout() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://embed.test")
    adapter = HttpEmbeddingAdapter(_settings(), client=client)
    with pytest.raises(EmbeddingAdapterError) as exc:
        await adapter.embed(EmbedTextInput(text="hello"))
    assert exc.value.code == "timeout"


async def test_http_embed_maps_model_missing_as_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://embed.test")
    adapter = HttpEmbeddingAdapter(_settings(), client=client)
    with pytest.raises(EmbeddingAdapterError) as exc:
        await adapter.embed(EmbedTextInput(text="hello"))
    assert exc.value.code == "unavailable"


async def test_http_embed_requires_api_key() -> None:
    adapter = HttpEmbeddingAdapter(_settings(api_key=""), client=httpx.AsyncClient())
    with pytest.raises(EmbeddingAdapterError) as exc:
        await adapter.embed(EmbedTextInput(text="hello"))
    assert exc.value.code == "unavailable"


async def test_http_embed_rejects_wrong_dimension() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [1.0]}]})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://embed.test")
    adapter = HttpEmbeddingAdapter(_settings(dim=4), client=client)
    with pytest.raises(EmbeddingAdapterError) as exc:
        await adapter.embed(EmbedTextInput(text="hello"))
    assert exc.value.code == "parse_error"
