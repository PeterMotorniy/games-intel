from __future__ import annotations

from typing import Protocol

from games_intel.contracts.adapters import (
    CanaryParseInput,
    CanaryParseResult,
    GameDetails,
    GameListing,
    GetGameInput,
    GetReviewsInput,
    ListBrowsePageInput,
    ListNewReleasesInput,
    ReviewBatch,
)


class MetacriticPort(Protocol):
    async def list_new_releases(self, inp: ListNewReleasesInput) -> GameListing: ...

    async def list_browse_page(self, inp: ListBrowsePageInput) -> GameListing: ...

    async def get_game(self, inp: GetGameInput) -> GameDetails: ...

    async def get_critic_reviews(self, inp: GetReviewsInput) -> ReviewBatch: ...

    async def get_user_reviews(self, inp: GetReviewsInput) -> ReviewBatch: ...

    async def canary_parse(self, inp: CanaryParseInput) -> CanaryParseResult: ...
