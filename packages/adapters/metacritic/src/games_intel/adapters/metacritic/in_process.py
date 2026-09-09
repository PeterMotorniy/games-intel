from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.parser import clip_review_batch
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


class InProcessMetacriticAdapter:
    """Test double: no Playwright and no HTTP sidecar."""

    def __init__(
        self,
        *,
        listings: Mapping[str, GameListing] | None = None,
        browse: Mapping[int, GameListing] | None = None,
        games: Mapping[str, GameDetails] | None = None,
        critic_reviews: Mapping[str, ReviewBatch] | None = None,
        user_reviews: Mapping[str, ReviewBatch] | None = None,
        canaries: Mapping[str, CanaryParseResult] | None = None,
        errors: Mapping[str, MetacriticAdapterError] | None = None,
    ) -> None:
        self._listings = dict(listings or {})
        self._browse = dict(browse or {})
        self._games = dict(games or {})
        self._critic_reviews = dict(critic_reviews or {})
        self._user_reviews = dict(user_reviews or {})
        self._canaries = dict(canaries or {})
        self._errors = dict(errors or {})
        self.calls: list[tuple[str, Any]] = []

    async def list_new_releases(self, inp: ListNewReleasesInput) -> GameListing:
        self.calls.append(("list_new_releases", inp))
        self._raise("list_new_releases")
        listing = self._listings.get("new_releases")
        if listing is None:
            raise MetacriticAdapterError("unavailable", "in_process listing is not configured")
        return listing.model_copy(update={"items": listing.items[: inp.limit]})

    async def list_browse_page(self, inp: ListBrowsePageInput) -> GameListing:
        self.calls.append(("list_browse_page", inp))
        self._raise("list_browse_page")
        listing = self._browse.get(inp.page)
        if listing is None:
            raise MetacriticAdapterError("unavailable", "in_process browse page is not configured")
        return listing.model_copy(update={"items": listing.items[: inp.limit]})

    async def get_game(self, inp: GetGameInput) -> GameDetails:
        self.calls.append(("get_game", inp))
        self._raise(f"get_game:{inp.slug}")
        self._raise("get_game")
        game = self._games.get(inp.slug)
        if game is None:
            raise MetacriticAdapterError("not_found", f"in_process game missing: {inp.slug}")
        return game

    async def get_critic_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        self.calls.append(("get_critic_reviews", inp))
        self._raise(f"get_critic_reviews:{inp.slug}")
        batch = self._critic_reviews.get(inp.slug)
        if batch is None:
            return ReviewBatch(items=[], truncated=False)
        return clip_review_batch(
            batch.items,
            limit=inp.limit,
            max_chars=inp.max_chars,
            already_truncated=batch.truncated,
        )

    async def get_user_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        self.calls.append(("get_user_reviews", inp))
        self._raise(f"get_user_reviews:{inp.slug}")
        batch = self._user_reviews.get(inp.slug)
        if batch is None:
            return ReviewBatch(items=[], truncated=False)
        return clip_review_batch(
            batch.items,
            limit=inp.limit,
            max_chars=inp.max_chars,
            already_truncated=batch.truncated,
        )

    async def canary_parse(self, inp: CanaryParseInput) -> CanaryParseResult:
        self.calls.append(("canary_parse", inp))
        self._raise(f"canary_parse:{inp.slug}")
        self._raise("canary_parse")
        result = self._canaries.get(inp.slug)
        if result is None:
            raise MetacriticAdapterError("unavailable", "in_process canary is not configured")
        return result

    def _raise(self, key: str) -> None:
        error = self._errors.get(key)
        if error is not None:
            raise error
