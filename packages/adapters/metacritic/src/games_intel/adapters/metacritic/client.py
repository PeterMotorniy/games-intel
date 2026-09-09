from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.contracts.adapters import (
    AdapterError,
    AdapterErrorCode,
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
from games_intel.settings import Settings

_STATUS_TO_CODE: dict[int, AdapterErrorCode] = {
    404: "not_found",
    408: "timeout",
    429: "rate_limited",
    422: "parse_error",
    503: "unavailable",
    504: "timeout",
}


class SidecarMetacriticClient:
    """HTTP client for the Playwright sidecar. Serializes the same Port DTOs."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        metacritic = settings.adapters.metacritic
        read_timeout = max(60.0, float(metacritic.timeout_seconds) * 3)
        timeout = httpx.Timeout(read_timeout)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=metacritic.sidecar_base_url.rstrip("/"),
            timeout=timeout,
        )
        self._timeout_seconds = metacritic.timeout_seconds

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_new_releases(self, inp: ListNewReleasesInput) -> GameListing:
        payload = await self._post("/v1/list_new_releases", inp.model_dump(mode="json"))
        return GameListing.model_validate(payload)

    async def list_browse_page(self, inp: ListBrowsePageInput) -> GameListing:
        payload = await self._post("/v1/list_browse_page", inp.model_dump(mode="json"))
        return GameListing.model_validate(payload)

    async def get_game(self, inp: GetGameInput) -> GameDetails:
        payload = await self._post("/v1/get_game", inp.model_dump(mode="json"))
        return GameDetails.model_validate(payload)

    async def get_critic_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        payload = await self._post("/v1/get_critic_reviews", inp.model_dump(mode="json"))
        return ReviewBatch.model_validate(payload)

    async def get_user_reviews(self, inp: GetReviewsInput) -> ReviewBatch:
        payload = await self._post("/v1/get_user_reviews", inp.model_dump(mode="json"))
        return ReviewBatch.model_validate(payload)

    async def canary_parse(self, inp: CanaryParseInput) -> CanaryParseResult:
        payload = await self._post("/v1/canary_parse", inp.model_dump(mode="json"))
        return CanaryParseResult.model_validate(payload)

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        try:
            response = await self._client.post(path, json=body)
        except httpx.TimeoutException as exc:
            raise MetacriticAdapterError("timeout", "sidecar request timed out") from exc
        except httpx.HTTPError as exc:
            raise MetacriticAdapterError("unavailable", "sidecar unavailable") from exc
        if response.status_code == 200:
            return response.json()
        try:
            error = AdapterError.model_validate(response.json())
        except (ValueError, ValidationError):
            code = _STATUS_TO_CODE.get(response.status_code, "unavailable")
            raise MetacriticAdapterError(code, f"sidecar HTTP {response.status_code}") from None
        raise MetacriticAdapterError.from_dto(error)
