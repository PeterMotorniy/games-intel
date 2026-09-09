from __future__ import annotations

from typing import Protocol

from games_intel.contracts.agents import LetsPlayAnalystInput, LetsPlayConclusion


class LetsPlayAnalystAgent(Protocol):
    async def ainvoke(self, inp: LetsPlayAnalystInput) -> LetsPlayConclusion: ...
