from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.adapters.metacritic.exceptions import MetacriticAdapterError
from games_intel.adapters.metacritic.port import MetacriticPort
from games_intel.agents.review_summarizer.exceptions import (
    LlmStructureError as AgentLlmStructureError,
)
from games_intel.agents.review_summarizer.exceptions import (
    LlmTransientError,
)
from games_intel.agents.review_summarizer.port import ReviewSummarizerAgent
from games_intel.contracts.adapters import GetReviewsInput, ReviewBatch
from games_intel.contracts.agents import ReviewSummarizerInput, ReviewSummarizerOutput
from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.ids import new_traceparent
from games_intel.contracts.payloads import GameCataloged, GameReviewsSummarized, ReviewSummary
from games_intel.db.exceptions import GameNotFoundError
from games_intel.db.records import OutboxInsert, ReviewsSlice
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.reviews import GameReviewsRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage
from games_intel.kafka.classify import map_adapter_error
from games_intel.kafka.exceptions import LlmStructureError, NotFoundError, TransientError
from games_intel.kafka.logging import emit_json
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.workers.reviews")

_WORKER_TYPE = "reviews"
_EMPTY_SUMMARY = ReviewSummary(likes=[], dislikes=[], summary="")


@dataclass(frozen=True, slots=True)
class _ReviewsPrepared:
    cataloged: GameCataloged
    output: ReviewSummarizerOutput
    critic_count: int
    user_count: int
    degraded: bool
    status: IngestionItemStatus


class ReviewsHandler:
    """Download review snippets via Port, optionally invoke summarizer, persist reviews slice."""

    def __init__(
        self, settings: Settings, port: MetacriticPort, agent: ReviewSummarizerAgent
    ) -> None:
        self.settings = settings
        self.port = port
        self.agent = agent

    async def prepare(self, event: CloudEvent[Any]) -> _ReviewsPrepared:
        cataloged = event.data
        if not isinstance(cataloged, GameCataloged):
            msg = "reviews expected GameCataloged payload"
            raise TypeError(msg)
        critic_batch, critic_transient = await self._get_reviews_side(
            cataloged.metacritic_slug, kind="critic"
        )
        user_batch, user_transient = await self._get_reviews_side(
            cataloged.metacritic_slug, kind="user"
        )
        if not critic_batch.items and not user_batch.items and (critic_transient or user_transient):
            raise TransientError("sidecar timeout fetching reviews")
        critic_empty = not critic_batch.items
        user_empty = not user_batch.items
        skip_empty = self.settings.reviews.skip_agent_if_empty
        if skip_empty and critic_empty and user_empty:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=cataloged.metacritic_slug,
                worker=_WORKER_TYPE,
                stage=self.settings.reviews.stage_name,
                event="reviews_empty_skip_agent",
                run_id=str(cataloged.run_id),
                event_id=event.id,
            )
            return _ReviewsPrepared(
                cataloged=cataloged,
                output=ReviewSummarizerOutput(critic=_EMPTY_SUMMARY, user=_EMPTY_SUMMARY),
                critic_count=0,
                user_count=0,
                degraded=True,
                status=IngestionItemStatus.degraded,
            )
        try:
            output = await self.agent.ainvoke(
                ReviewSummarizerInput(
                    run_id=cataloged.run_id,
                    metacritic_slug=cataloged.metacritic_slug,
                    critic=list(critic_batch.items),
                    user=list(user_batch.items),
                )
            )
        except AgentLlmStructureError as exc:
            raise LlmStructureError(str(exc)) from exc
        except LlmTransientError as exc:
            raise TransientError(str(exc)) from exc
        if skip_empty and critic_empty:
            output = output.model_copy(update={"critic": _EMPTY_SUMMARY})
        if skip_empty and user_empty:
            output = output.model_copy(update={"user": _EMPTY_SUMMARY})
        degraded = bool(skip_empty and (critic_empty or user_empty))
        status = IngestionItemStatus.degraded if degraded else IngestionItemStatus.completed
        return _ReviewsPrepared(
            cataloged=cataloged,
            output=output,
            critic_count=len(critic_batch.items),
            user_count=len(user_batch.items),
            degraded=degraded,
            status=status,
        )

    async def persist(
        self, event: CloudEvent[Any], session: AsyncSession, prepared: _ReviewsPrepared
    ) -> None:
        cataloged = prepared.cataloged
        try:
            game_id = await GameReviewsRepository(session).update_reviews(
                _reviews_slice(cataloged.metacritic_slug, prepared.output)
            )
        except GameNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        await IngestionRepository(session).upsert_item(
            run_id=cataloged.run_id,
            metacritic_slug=cataloged.metacritic_slug,
            process_date=cataloged.process_date,
            stage=IngestionStage.reviews,
            status=prepared.status,
            game_id=game_id,
            event_id=event.id,
        )
        await _enqueue_reviews_summarized(
            session,
            self.settings,
            cataloged=cataloged,
            output=prepared.output,
            critic_count=prepared.critic_count,
            user_count=prepared.user_count,
            degraded=prepared.degraded,
        )

    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None:
        prepared = await self.prepare(event)
        await self.persist(event, session, prepared)

    async def _get_reviews_side(
        self, slug: str, *, kind: Literal["critic", "user"]
    ) -> tuple[ReviewBatch, bool]:
        try:
            return await self._get_reviews(slug, kind=kind), False
        except TransientError:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=slug,
                worker=_WORKER_TYPE,
                stage=self.settings.reviews.stage_name,
                event="reviews_side_transient",
                kind=kind,
            )
            return ReviewBatch(items=[], truncated=False), True

    async def _get_reviews(self, slug: str, *, kind: Literal["critic", "user"]) -> ReviewBatch:
        reviews = self.settings.reviews
        inp = GetReviewsInput(
            slug=slug,
            limit=reviews.critic_limit if kind == "critic" else reviews.user_limit,
            max_chars=reviews.max_chars,
        )
        try:
            if kind == "critic":
                return await self.port.get_critic_reviews(inp)
            return await self.port.get_user_reviews(inp)
        except MetacriticAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc


def _reviews_slice(slug: str, output: ReviewSummarizerOutput) -> ReviewsSlice:
    return ReviewsSlice(
        metacritic_slug=slug,
        critic_likes=tuple(output.critic.likes),
        critic_dislikes=tuple(output.critic.dislikes),
        critic_summary=output.critic.summary,
        user_likes=tuple(output.user.likes),
        user_dislikes=tuple(output.user.dislikes),
        user_summary=output.user.summary,
    )


async def _enqueue_reviews_summarized(
    session: AsyncSession,
    settings: Settings,
    *,
    cataloged: GameCataloged,
    output: ReviewSummarizerOutput,
    critic_count: int,
    user_count: int,
    degraded: bool,
) -> None:
    payload = GameReviewsSummarized(
        run_id=cataloged.run_id,
        metacritic_slug=cataloged.metacritic_slug,
        critic=output.critic,
        user=output.user,
        critic_review_count=critic_count,
        user_review_count=user_count,
        degraded=degraded,
    )
    event = build_cloud_event(
        settings,
        settings.reviews.publish_event,
        source=worker_source(settings, _WORKER_TYPE),
        subject=cataloged.metacritic_slug,
        data=payload,
        stage=settings.reviews.stage_name,
        run_id=cataloged.run_id,
        traceparent=new_traceparent(),
    )
    await OutboxRepository(session).insert(
        OutboxInsert(
            producer=_WORKER_TYPE,
            idempotency_key=event.idempotencykey,
            topic=settings.event_name(settings.reviews.publish_event),
            partition_key=cataloged.metacritic_slug,
            payload=cloud_event_to_dict(event),
        )
    )
