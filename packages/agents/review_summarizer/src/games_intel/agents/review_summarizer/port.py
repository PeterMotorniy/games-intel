from __future__ import annotations

from typing import Protocol

from games_intel.contracts.agents import ReviewSummarizerInput, ReviewSummarizerOutput


class ReviewSummarizerAgent(Protocol):
    async def ainvoke(self, inp: ReviewSummarizerInput) -> ReviewSummarizerOutput: ...
