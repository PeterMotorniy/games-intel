from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from games_intel.api.errors import ProblemError
from games_intel.api.schemas import MonitorSnapshot, RunAcceptedResponse
from games_intel.api.services import MonitorQueryService, RunCommandService
from games_intel.settings import Settings

_NO_STORE = {"Cache-Control": "no-store"}
SleepFn = Callable[[float], Awaitable[None]]
DisconnectedFn = Callable[[], Awaitable[bool]]
SnapshotFn = Callable[[], Awaitable[MonitorSnapshot]]


async def iter_monitor_sse_frames(
    snapshot: SnapshotFn,
    *,
    poll_seconds: float,
    disconnected: DisconnectedFn,
    sleep: SleepFn | None = None,
) -> AsyncIterator[bytes]:
    pause = sleep if sleep is not None else asyncio.sleep
    last = ""
    while True:
        if await disconnected():
            break
        payload = (await snapshot()).model_dump_json()
        if payload != last:
            yield f"data: {payload}\n\n".encode()
            last = payload
        await pause(poll_seconds)


def create_monitor_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["monitor"])
    poll_seconds = max(float(settings.monitor.sse_poll_seconds), 0.2)

    @router.get("/monitor", response_model=MonitorSnapshot)
    async def get_monitor(request: Request, response: Response) -> MonitorSnapshot:
        response.headers["Cache-Control"] = "no-store"
        monitor: MonitorQueryService = request.app.state.monitor
        return await monitor.snapshot()

    @router.get(
        "/monitor/stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "SSE кадры снимка монитора",
                "content": {"text/event-stream": {"schema": {"type": "string"}}},
            }
        },
    )
    async def stream_monitor(request: Request) -> StreamingResponse:
        monitor: MonitorQueryService = request.app.state.monitor

        async def frames() -> AsyncIterator[bytes]:
            async for chunk in iter_monitor_sse_frames(
                monitor.snapshot,
                poll_seconds=poll_seconds,
                disconnected=request.is_disconnected,
            ):
                yield chunk

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={
                **_NO_STORE,
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/runs", status_code=202, response_model=RunAcceptedResponse)
    async def start_run(request: Request, response: Response) -> RunAcceptedResponse:
        response.headers["Cache-Control"] = "no-store"
        _require_command_auth(request, settings)
        _enforce_command_rate_limit(request, settings)
        runs: RunCommandService = request.app.state.runs
        return await runs.accept_manual_run()

    return router


def _require_command_auth(request: Request, settings: Settings) -> None:
    token = settings.api.command_token.get_secret_value().strip()
    if not token:
        return
    header = request.headers.get("x-api-key") or request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        offered = header.removeprefix("Bearer ").strip()
    else:
        offered = header
    if offered != token:
        raise ProblemError(401, "Unauthorized", "command token required")


def _enforce_command_rate_limit(request: Request, settings: Settings) -> None:
    limit = max(int(settings.api.command_rate_limit_per_minute), 0)
    if limit <= 0:
        return
    bucket: dict[str, list[float]] = getattr(request.app.state, "run_rate_limit", None) or {}
    request.app.state.run_rate_limit = bucket
    key = request.client.host if request.client is not None else "unknown"
    now = datetime.now(UTC).timestamp()
    window = [stamp for stamp in bucket.get(key, []) if now - stamp < 60]
    if len(window) >= limit:
        raise ProblemError(429, "Too Many Requests", "run command rate limit exceeded")
    window.append(now)
    bucket[key] = window
