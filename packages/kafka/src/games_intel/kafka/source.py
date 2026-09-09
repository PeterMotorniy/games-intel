from __future__ import annotations

from games_intel.settings import Settings


def worker_source(settings: Settings, worker_type: str) -> str:
    return f"urn:{settings.app.name}:worker:{worker_type}"


def api_source(settings: Settings) -> str:
    return f"urn:{settings.app.name}:api"


def resolve_client_id(settings: Settings, worker_type: str, instance_id: str) -> str:
    return (
        settings.kafka.client_id.replace("{app.name}", settings.app.name)
        .replace("{worker.type}", worker_type)
        .replace("{instance_id}", instance_id)
    )
