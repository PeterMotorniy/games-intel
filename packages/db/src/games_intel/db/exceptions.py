from __future__ import annotations

from uuid import UUID


class GamesIntelDbError(Exception):
    """Base error for the database package."""


class GameNotFoundError(GamesIntelDbError):
    def __init__(self, metacritic_slug: str) -> None:
        self.metacritic_slug = metacritic_slug
        super().__init__(f"game not found: {metacritic_slug}")


class SimilarGameSelfReferenceError(GamesIntelDbError):
    def __init__(self, game_id: UUID) -> None:
        self.game_id = game_id
        super().__init__(f"similar_games cannot reference self: {game_id}")
