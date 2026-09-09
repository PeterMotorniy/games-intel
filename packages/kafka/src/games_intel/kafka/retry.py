from __future__ import annotations

import random

from games_intel.settings.config import RetrySettings


def backoff_seconds(
    attempt: int, retry: RetrySettings, *, rng: random.Random | None = None
) -> float:
    """Exponential backoff: base * 2^(n-1), capped, with ±jitter_ratio."""
    n = max(attempt, 1)
    delay = retry.backoff_base_seconds * (2 ** (n - 1))
    delay = min(delay, retry.backoff_max_seconds)
    jitter_source = rng if rng is not None else random
    jitter = delay * retry.jitter_ratio * (2 * jitter_source.random() - 1)
    return float(max(0.0, delay + jitter))
