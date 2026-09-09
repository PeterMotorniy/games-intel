from __future__ import annotations

from games_intel.adapters.metacritic.client import SidecarMetacriticClient
from games_intel.adapters.metacritic.in_process import InProcessMetacriticAdapter
from games_intel.adapters.metacritic.port import MetacriticPort
from games_intel.settings import Settings


def create_metacritic_port(
    settings: Settings,
    *,
    in_process: MetacriticPort | None = None,
) -> MetacriticPort:
    if settings.adapters.metacritic.mode == "in_process":
        return in_process if in_process is not None else InProcessMetacriticAdapter()
    return SidecarMetacriticClient(settings)
