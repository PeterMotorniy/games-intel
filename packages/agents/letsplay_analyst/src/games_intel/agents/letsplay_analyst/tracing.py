from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from games_intel.agents.letsplay_analyst.checkpoint import AGENT_NAME
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.agents.letsplay_analyst")

CallbacksFactory = Callable[[], Sequence[Any]]


def build_tracing_callbacks(_settings: Settings) -> list[Any]:
    return []


def safe_callbacks(factory: CallbacksFactory) -> list[Any]:
    try:
        return list(factory())
    except Exception:
        logger.warning(
            "tracing callbacks failed; continuing without callbacks",
            extra={"event": "tracing_degraded", "agent": AGENT_NAME},
            exc_info=True,
        )
        return []
