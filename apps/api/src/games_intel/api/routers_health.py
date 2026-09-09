from __future__ import annotations

from fastapi import APIRouter, Request

from games_intel.api.errors import DatabaseUnavailableError
from games_intel.api.schemas import LivenessResponse, ReadinessResponse
from games_intel.api.services import HealthService


def create_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/healthz", response_model=LivenessResponse)
    async def healthz() -> LivenessResponse:
        return LivenessResponse()

    @router.get("/readyz", response_model=ReadinessResponse)
    async def readyz(request: Request) -> ReadinessResponse:
        health: HealthService = request.app.state.health
        postgres = await health.postgres_ok()
        kafka = await health.kafka_ok()
        if not postgres:
            raise DatabaseUnavailableError
        return ReadinessResponse(status="ok", postgres=True, kafka=kafka)

    return router
