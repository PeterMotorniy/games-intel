from __future__ import annotations

from typing import Protocol

from games_intel.contracts.agents import TranscriptionInput, TranscriptionOutput


class TranscriptionAgent(Protocol):
    async def ainvoke(self, inp: TranscriptionInput) -> TranscriptionOutput: ...
