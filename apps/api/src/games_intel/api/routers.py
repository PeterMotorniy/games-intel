from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from games_intel.api.errors import ProblemError
from games_intel.api.schemas import (
    GameCardRead,
    GameListResponse,
    GameSortName,
    PlatformListResponse,
    SortOrderName,
)
from games_intel.api.services import CatalogQueryService, CoverQueryService
from games_intel.settings import Settings


def create_catalog_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["games"])
    default_size = settings.api.page_size_default
    max_size = settings.api.page_size_max

    @router.get("/games", response_model=GameListResponse)
    async def list_games(
        request: Request,
        q: str | None = None,
        platform: str | None = None,
        sort: GameSortName = "metascore",
        order: SortOrderName = "desc",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=default_size, ge=1),
    ) -> GameListResponse:
        if page_size > max_size:
            raise ProblemError(
                400,
                "Bad Request",
                f"page_size must be <= {max_size}",
            )
        catalog: CatalogQueryService = request.app.state.catalog
        return await catalog.list_games(
            q=q,
            platform=platform,
            sort=sort,
            order=order,
            page=page,
            page_size=page_size,
        )

    @router.get("/games/{slug}", response_model=GameCardRead)
    async def get_game(slug: str, request: Request) -> GameCardRead:
        catalog: CatalogQueryService = request.app.state.catalog
        return await catalog.get_game(slug)

    @router.get("/platforms", response_model=PlatformListResponse, tags=["platforms"])
    async def list_platforms(request: Request) -> PlatformListResponse:
        catalog: CatalogQueryService = request.app.state.catalog
        return await catalog.list_platforms()

    return router


def create_media_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["media"])

    @router.get(
        "/media/covers/{slug}",
        responses={
            200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}},
            404: {"description": "Cover file is missing"},
        },
    )
    async def get_cover(slug: str, request: Request) -> Response:
        covers: CoverQueryService = request.app.state.covers
        data, media_type, cache_control = await covers.load(slug)
        return Response(
            content=data,
            media_type=media_type,
            headers={"Cache-Control": cache_control},
        )

    return router
