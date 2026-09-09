from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any

from games_intel.agents.transcription.checkpoint import AGENT_NAME
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.agents.transcription")


@contextmanager
def tracing_span(_settings: Settings, *, thread_id: str) -> Iterator[None]:
    del thread_id
    yield


def safe_tracing_span(settings: Settings, *, thread_id: str) -> Any:
    try:
        return tracing_span(settings, thread_id=thread_id)
    except Exception:
        logger.warning(
            "tracing span failed; continuing without span",
            extra={"event": "tracing_degraded", "agent": AGENT_NAME},
            exc_info=True,
        )
        return nullcontext()
