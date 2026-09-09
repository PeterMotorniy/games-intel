from __future__ import annotations

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.db.exceptions import GameNotFoundError
from games_intel.db.mapping import utcnow
from games_intel.db.models import Game
from games_intel.db.records import LetsPlaySlice


class GameLetsPlayRepository:
    """Writes only letsplay_* columns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def update_letsplay(self, slice_: LetsPlaySlice) -> UUID:
        status = None if slice_.status is None else slice_.status.value
        stmt = (
            update(Game)
            .where(Game.metacritic_slug == slice_.metacritic_slug)
            .values(
                letsplay_status=status,
                letsplay_video_url=slice_.video_url,
                letsplay_video_title=slice_.video_title,
                letsplay_view_count=slice_.view_count,
                letsplay_conclusion=slice_.conclusion,
                letsplay_highlights=(
                    None if slice_.highlights is None else list(slice_.highlights)
                ),
                updated_at=utcnow(),
            )
            .returning(Game.id)
        )
        updated_id = (await self._session.execute(stmt)).scalar_one_or_none()
        if updated_id is None:
            raise GameNotFoundError(slice_.metacritic_slug)
        return updated_id
