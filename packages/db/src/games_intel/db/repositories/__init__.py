from __future__ import annotations

from games_intel.db.repositories.catalog import GameCatalogRepository
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.letsplay import GameLetsPlayRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.page_cache import PageCacheRepository
from games_intel.db.repositories.reviews import GameReviewsRepository
from games_intel.db.repositories.similar import SimilarGamesRepository

__all__ = [
    "GameCatalogRepository",
    "GameLetsPlayRepository",
    "GameReviewsRepository",
    "IngestionRepository",
    "OutboxRepository",
    "PageCacheRepository",
    "SimilarGamesRepository",
]
