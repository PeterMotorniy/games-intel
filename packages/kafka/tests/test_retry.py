from __future__ import annotations

import random

from games_intel.kafka.retry import backoff_seconds
from games_intel.settings.config import RetrySettings


def test_backoff_exponential_capped() -> None:
    retry = RetrySettings(backoff_base_seconds=1, backoff_max_seconds=8, jitter_ratio=0)
    rng = random.Random(0)
    assert backoff_seconds(1, retry, rng=rng) == 1
    rng = random.Random(0)
    assert backoff_seconds(2, retry, rng=rng) == 2
    rng = random.Random(0)
    assert backoff_seconds(3, retry, rng=rng) == 4
    rng = random.Random(0)
    assert backoff_seconds(4, retry, rng=rng) == 8
    rng = random.Random(0)
    assert backoff_seconds(5, retry, rng=rng) == 8
