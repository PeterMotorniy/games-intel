from __future__ import annotations

import httpx

from games_intel.adapters.embeddings.http import HttpEmbeddingAdapter
from games_intel.adapters.embeddings.port import EmbeddingPort
from games_intel.settings import Settings


def create_embedding_port(
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> EmbeddingPort:
    return HttpEmbeddingAdapter(settings, client=client)
