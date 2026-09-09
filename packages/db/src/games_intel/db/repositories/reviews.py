from __future__ import annotations

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.db.exceptions import GameNotFoundError
from games_intel.db.mapping import utcnow
from games_intel.db.models import Game
from games_intel.db.records import ReviewsSlice


class GameReviewsRepository:
    """Writes only review summary columns. Never updates cover or catalog fields."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def update_reviews(self, slice_: ReviewsSlice) -> UUID:
        stmt = (
            update(Game)
            .where(Game.metacritic_slug == slice_.metacritic_slug)
            .values(
                critic_likes=None if slice_.critic_likes is None else list(slice_.critic_likes),
                critic_dislikes=(
                    None if slice_.critic_dislikes is None else list(slice_.critic_dislikes)
                ),
                critic_summary=slice_.critic_summary,
                user_likes=None if slice_.user_likes is None else list(slice_.user_likes),
                user_dislikes=None if slice_.user_dislikes is None else list(slice_.user_dislikes),
                user_summary=slice_.user_summary,
                updated_at=utcnow(),
            )
            .returning(Game.id)
        )
        updated_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if updated_id is None:
            raise GameNotFoundError(slice_.metacritic_slug)
        return updated_id
