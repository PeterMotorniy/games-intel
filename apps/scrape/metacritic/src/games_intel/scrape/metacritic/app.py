from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from games_intel.adapters.metacritic.cache import MemoryPageCache
from games_intel.adapters.metacritic.circuit import CircuitBreaker, CircuitSnapshot
from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.contracts.adapters import (
    AdapterError,
    CanaryParseInput,
    GetGameInput,
    GetReviewsInput,
    ListBrowsePageInput,
    ListNewReleasesInput,
)
from games_intel.scrape.metacritic.service import MemoryHealthSink, ScrapeService
from games_intel.settings import Settings, load_settings

_HTTP_STATUS: dict[str, int] = {
    "not_found": 404,
    "timeout": 504,
    "rate_limited": 429,
    "parse_error": 422,
    "quota_exceeded": 429,
    "unavailable": 503,
    "circuit_open": 503,
}


def create_app(
    settings: Settings | None = None,
    *,
    service: ScrapeService | None = None,
) -> FastAPI:
    loaded = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = loaded
        if service is not None:
            app.state.service = service
            yield
            return
        runtime = await _build_runtime(loaded)
        app.state.service = runtime["service"]
        app.state.fetcher = runtime.get("fetcher")
        app.state.engine = runtime.get("engine")
        try:
            yield
        finally:
            fetcher = getattr(app.state, "fetcher", None)
            if fetcher is not None:
                close = getattr(fetcher, "close", None)
                if close is not None:
                    await close()
            engine = getattr(app.state, "engine", None)
            if engine is not None:
                await engine.dispose()

    app = FastAPI(title="games-intel-scrape-metacritic", lifespan=lifespan)
    app.state.settings = loaded
    if service is not None:
        app.state.service = service

    @app.exception_handler(MetacriticAdapterError)
    async def adapter_error_handler(_request: Request, exc: MetacriticAdapterError) -> JSONResponse:
        dto = AdapterError(code=exc.code, message=exc.message)
        return JSONResponse(status_code=_HTTP_STATUS.get(exc.code, 503), content=dto.model_dump())

    @app.get("/healthz")
    async def healthz(request: Request) -> dict[str, str]:
        current: ScrapeService = request.app.state.service
        snapshot: CircuitSnapshot = current.circuit.snapshot
        return {
            "status": "ok",
            "circuit_state": snapshot.state,
        }

    @app.post("/v1/list_new_releases")
    async def list_new_releases(inp: ListNewReleasesInput, request: Request) -> Any:
        return (await _service(request).list_new_releases(inp)).model_dump(mode="json")

    @app.post("/v1/list_browse_page")
    async def list_browse_page(inp: ListBrowsePageInput, request: Request) -> Any:
        return (await _service(request).list_browse_page(inp)).model_dump(mode="json")

    @app.post("/v1/get_game")
    async def get_game(inp: GetGameInput, request: Request) -> Any:
        return (await _service(request).get_game(inp)).model_dump(mode="json")

    @app.post("/v1/get_critic_reviews")
    async def get_critic_reviews(inp: GetReviewsInput, request: Request) -> Any:
        return (await _service(request).get_critic_reviews(inp)).model_dump(mode="json")

    @app.post("/v1/get_user_reviews")
    async def get_user_reviews(inp: GetReviewsInput, request: Request) -> Any:
        return (await _service(request).get_user_reviews(inp)).model_dump(mode="json")

    @app.post("/v1/canary_parse")
    async def canary_parse(inp: CanaryParseInput, request: Request) -> Any:
        return (await _service(request).canary_parse(inp)).model_dump(mode="json")

    return app


def _service(request: Request) -> ScrapeService:
    return cast(ScrapeService, request.app.state.service)


async def _build_runtime(settings: Settings) -> dict[str, Any]:
    from games_intel.db.engine import (
        create_engine,
        create_session_factory,
        wait_until_database_ready,
    )
    from games_intel.db.repositories.ingestion import IngestionRepository
    from games_intel.scrape.metacritic.browser import PlaywrightFetcher
    from games_intel.scrape.metacritic.stores import PostgresHealthSink, PostgresPageCache

    meta = settings.adapters.metacritic
    fetcher = PlaywrightFetcher(settings)
    await fetcher.start()
    engine = None
    session_factory = None
    initial: CircuitSnapshot | None = None
    cache: MemoryPageCache | PostgresPageCache
    health: MemoryHealthSink | PostgresHealthSink
    database_url = settings.database.url.get_secret_value().strip()
    if not database_url:
        cache = MemoryPageCache()
        health = MemoryHealthSink()
    else:
        engine = create_engine(settings)
        if not await wait_until_database_ready(engine):
            await fetcher.close()
            await engine.dispose()
            msg = "scrape sidecar not ready: database unavailable"
            raise RuntimeError(msg)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            health_row = await IngestionRepository(session).get_adapter_health("metacritic")
            if health_row is not None:
                initial = CircuitSnapshot(
                    state=health_row.circuit_state,
                    parse_error_streak=health_row.parse_error_streak,
                    opened_at=health_row.opened_at,
                    last_parse_error_at=health_row.last_parse_error_at,
                )
        cache = PostgresPageCache(session_factory)
        health = PostgresHealthSink(session_factory)
    circuit = CircuitBreaker(
        fail_threshold=meta.circuit_fail_threshold,
        open_seconds=meta.circuit_open_seconds,
        initial=initial,
    )
    service = ScrapeService(
        meta,
        fetcher=fetcher,
        cache=cache,
        circuit=circuit,
        health=health,
    )
    return {"service": service, "fetcher": fetcher, "engine": engine}
