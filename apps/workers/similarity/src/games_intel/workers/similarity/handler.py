from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.adapters.embeddings.exceptions import EmbeddingAdapterError
from games_intel.adapters.embeddings.port import EmbeddingPort
from games_intel.contracts.adapters import EmbedTextInput
from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.payloads import (
    GameCataloged,
    GameReviewsSummarized,
    GameSimilarAssigned,
    SimilarGameRef,
    SimilarityRecomputeRequested,
)
from games_intel.db.exceptions import GameNotFoundError
from games_intel.db.records import OutboxInsert, SimilarityGame
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.repositories.similar import SimilarGamesRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage
from games_intel.kafka.classify import map_adapter_error
from games_intel.kafka.exceptions import NotFoundError
from games_intel.kafka.logging import emit_json
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings
from games_intel.workers.similarity.scoring import (
    neighbors_from_matches,
    refs_from_matches,
    top_k,
)
from games_intel.workers.similarity.text import canonical_embedding_text, embedding_input_hash

logger = logging.getLogger("games_intel.workers.similarity")

_WORKER_TYPE = "similarity"
RecomputeReason = Literal["cataloged", "reviews", "schedule", "manual"]


@dataclass(frozen=True, slots=True)
class _SimilarityPrepared:
    data: Any
    slug: str | None = None
    vector: list[float] | None = None
    digest: str | None = None
    degraded: bool = False
    skip: bool = False


class SimilarityHandler:
    """Hybrid kNN from own DB. Embedding adapter only; no LangGraph."""

    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingPort,
        *,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self._sessions = session_factory

    async def prepare(self, event: CloudEvent[Any]) -> _SimilarityPrepared:
        data = event.data
        if (
            isinstance(data, GameReviewsSummarized)
            and not self.settings.similarity.recompute_on_reviews
        ):
            return _SimilarityPrepared(data=data, skip=True)
        if isinstance(data, SimilarityRecomputeRequested):
            if data.scope == "all":
                await self._embed_missing_games()
                return _SimilarityPrepared(data=data)
            if data.scope == "neighbors":
                return _SimilarityPrepared(data=data)
            if data.center_slug is None:
                return _SimilarityPrepared(data=data, skip=True)
        slug = _event_slug(data)
        if slug is None:
            msg = "similarity expected cataloged, reviews.summarized, or recompute payload"
            raise TypeError(msg)
        text = ""
        digest = ""
        async with self._sessions() as session:
            async with session.begin():
                game = await SimilarGamesRepository(session).get_similarity_game(slug)
                if game is None:
                    raise NotFoundError(f"game not found: {slug}") from GameNotFoundError(slug)
                include_reviews = self.settings.similarity.recompute_on_reviews
                text = canonical_embedding_text(game, include_reviews=include_reviews)
                digest = embedding_input_hash(
                    text,
                    model=self.settings.embeddings.model,
                    vector_dim=self.settings.embeddings.vector_dim,
                )
                if game.embedding is not None and game.embedding_input_hash == digest:
                    return _SimilarityPrepared(data=data, slug=slug)
                if not text:
                    return _SimilarityPrepared(data=data, slug=slug, degraded=True)
        try:
            result = await self.embeddings.embed(EmbedTextInput(text=text))
        except EmbeddingAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc
        return _SimilarityPrepared(data=data, slug=slug, vector=list(result.vector), digest=digest)

    async def persist(
        self, event: CloudEvent[Any], session: AsyncSession, prepared: _SimilarityPrepared
    ) -> None:
        if prepared.skip:
            return
        data = prepared.data
        if isinstance(data, SimilarityRecomputeRequested) and data.scope in {"all", "neighbors"}:
            await self._on_recompute(session, event, data)
            return
        slug = prepared.slug
        if slug is None:
            msg = "similarity game event missing slug"
            raise TypeError(msg)
        if prepared.vector is not None and prepared.digest is not None:
            await SimilarGamesRepository(session).upsert_embedding_by_slug(
                slug, embedding=prepared.vector, input_hash=prepared.digest
            )
        run_id, reason, fan_out, process_date = _game_event_meta(data)
        await self._on_game_event(
            session,
            event,
            slug=slug,
            run_id=run_id,
            reason=reason,
            fan_out=fan_out,
            process_date=process_date,
            skip_ensure=True,
            force_degraded=prepared.degraded,
        )

    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None:
        prepared = await self.prepare(event)
        await self.persist(event, session, prepared)

    async def _on_recompute(
        self,
        session: AsyncSession,
        event: CloudEvent[Any],
        data: SimilarityRecomputeRequested,
    ) -> None:
        if data.scope == "all":
            await self._recompute_all(session, event, data)
            return
        if data.scope == "neighbors":
            await self._recompute_slugs(
                session,
                event,
                slugs=data.candidate_slugs,
                run_id=data.run_id,
                process_date=data.process_date,
            )
            return
        if data.center_slug is None:
            return
        await self._on_game_event(
            session,
            event,
            slug=data.center_slug,
            run_id=data.run_id,
            reason=data.reason,
            fan_out=False,
            process_date=data.process_date,
        )

    async def _on_game_event(
        self,
        session: AsyncSession,
        event: CloudEvent[Any],
        *,
        slug: str,
        run_id: UUID | None,
        reason: RecomputeReason,
        fan_out: bool,
        process_date: date | None = None,
        skip_ensure: bool = False,
        force_degraded: bool = False,
    ) -> None:
        similar = SimilarGamesRepository(session)
        game = await similar.get_similarity_game(slug)
        if game is None:
            raise NotFoundError(f"game not found: {slug}") from GameNotFoundError(slug)
        if force_degraded:
            degraded = True
        elif skip_ensure:
            degraded = game.embedding is None
        else:
            game, degraded = await self._ensure_embedding(similar, game)
        resolved_date = await self._process_date(session, run_id, process_date)
        if degraded or game.embedding is None:
            await similar.replace_for_game(game.id, ())
            await self._mark_item(
                session,
                run_id=run_id,
                slug=slug,
                process_date=resolved_date,
                event_id=event.id,
                status=IngestionItemStatus.degraded,
            )
            await self._enqueue_assigned(
                session,
                run_id=run_id,
                slug=slug,
                items=[],
            )
            emit_json(
                logger,
                level=logging.WARNING,
                slug=slug,
                worker=_WORKER_TYPE,
                stage=self.settings.similarity.stage_name,
                event="embedding_missing_degraded",
                run_id=str(run_id) if run_id is not None else None,
                event_id=event.id,
            )
            return
        mode = self._resolve_mode(await similar.count_embedded(), fan_out=fan_out)
        if mode == "inline_all":
            assigned = await self._recompute_corpus(
                similar,
                initiator_slug=slug,
                emit_all=self.settings.similarity.emit_assigned_for_all,
            )
            for assigned_slug, refs in assigned:
                await self._enqueue_assigned(session, run_id=run_id, slug=assigned_slug, items=refs)
        else:
            corpus = await similar.list_embedded_games()
            current = _require_in_corpus(corpus, slug)
            matches = top_k(current, corpus, self.settings.similarity, k=self.settings.similarity.k)
            await similar.replace_for_game(current.id, neighbors_from_matches(matches))
            await self._enqueue_assigned(
                session, run_id=run_id, slug=slug, items=refs_from_matches(matches)
            )
            if fan_out:
                await self._enqueue_neighbors_recompute(
                    session,
                    game=current,
                    process_date=resolved_date,
                    run_id=run_id,
                    reason=reason,
                )
        await self._mark_item(
            session,
            run_id=run_id,
            slug=slug,
            process_date=resolved_date,
            event_id=event.id,
            status=IngestionItemStatus.completed,
        )

    async def _recompute_all(
        self,
        session: AsyncSession,
        event: CloudEvent[Any],
        data: SimilarityRecomputeRequested,
    ) -> None:
        similar = SimilarGamesRepository(session)
        assigned = await self._recompute_corpus(
            similar,
            initiator_slug=None,
            emit_all=self.settings.similarity.emit_assigned_for_all,
        )
        for slug, refs in assigned:
            await self._enqueue_assigned(session, run_id=data.run_id, slug=slug, items=refs)
        emit_json(
            logger,
            slug=event.subject,
            worker=_WORKER_TYPE,
            stage=self.settings.similarity.stage_name,
            event="full_recompute",
            event_id=event.id,
        )

    async def _recompute_slugs(
        self,
        session: AsyncSession,
        event: CloudEvent[Any],
        *,
        slugs: Sequence[str],
        run_id: UUID | None,
        process_date: date,
    ) -> None:
        similar = SimilarGamesRepository(session)
        corpus = await similar.list_embedded_games()
        by_slug = {item.metacritic_slug: item for item in corpus}
        for slug in slugs:
            game = by_slug.get(slug)
            if game is None or game.embedding is None:
                continue
            matches = top_k(game, corpus, self.settings.similarity, k=self.settings.similarity.k)
            await similar.replace_for_game(game.id, neighbors_from_matches(matches))
            await self._enqueue_assigned(
                session, run_id=run_id, slug=slug, items=refs_from_matches(matches)
            )
            await self._mark_item(
                session,
                run_id=run_id,
                slug=slug,
                process_date=process_date,
                event_id=event.id,
                status=IngestionItemStatus.completed,
            )

    async def _recompute_corpus(
        self,
        similar: SimilarGamesRepository,
        *,
        initiator_slug: str | None,
        emit_all: bool,
    ) -> list[tuple[str, list[SimilarGameRef]]]:
        corpus = await similar.list_embedded_games()
        items_by_game = {}
        assigned: list[tuple[str, list[SimilarGameRef]]] = []
        k = self.settings.similarity.k
        weights = self.settings.similarity
        for game in corpus:
            matches = top_k(game, corpus, weights, k=k)
            items_by_game[game.id] = neighbors_from_matches(matches)
            if emit_all or game.metacritic_slug == initiator_slug:
                assigned.append((game.metacritic_slug, refs_from_matches(matches)))
        await similar.replace_all(items_by_game)
        return assigned

    async def _embed_missing_games(self) -> None:
        async with self._sessions() as session:
            async with session.begin():
                slugs = [
                    game.metacritic_slug
                    for game in await SimilarGamesRepository(session).list_all_games()
                ]
        for slug in slugs:
            async with self._sessions() as session:
                async with session.begin():
                    similar = SimilarGamesRepository(session)
                    game = await similar.get_similarity_game(slug)
                    if game is None:
                        continue
                    await self._ensure_embedding(similar, game)

    async def _ensure_embedding(
        self, similar: SimilarGamesRepository, game: SimilarityGame
    ) -> tuple[SimilarityGame, bool]:
        include_reviews = self.settings.similarity.recompute_on_reviews
        text = canonical_embedding_text(game, include_reviews=include_reviews)
        digest = embedding_input_hash(
            text,
            model=self.settings.embeddings.model,
            vector_dim=self.settings.embeddings.vector_dim,
        )
        if game.embedding is not None and game.embedding_input_hash == digest:
            return game, False
        if not text:
            return game, True
        try:
            result = await self.embeddings.embed(EmbedTextInput(text=text))
        except EmbeddingAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc
        await similar.upsert_embedding_by_slug(
            game.metacritic_slug, embedding=result.vector, input_hash=digest
        )
        refreshed = await similar.get_similarity_game(game.metacritic_slug)
        if refreshed is None or refreshed.embedding is None:
            return game, True
        return refreshed, False

    def _resolve_mode(
        self, embedded_count: int, *, fan_out: bool
    ) -> Literal["inline_all", "incremental"]:
        if not fan_out:
            return "incremental"
        if self.settings.similarity.mode == "incremental":
            return "incremental"
        if embedded_count >= self.settings.similarity.inline_all_max_rows:
            return "incremental"
        return "inline_all"

    async def _enqueue_neighbors_recompute(
        self,
        session: AsyncSession,
        *,
        game: SimilarityGame,
        process_date: date | None,
        run_id: UUID | None,
        reason: RecomputeReason,
    ) -> None:
        if game.embedding is None or process_date is None:
            return
        similar = SimilarGamesRepository(session)
        nearest = await similar.nearest_slugs_by_vector(
            game.embedding,
            limit=self.settings.similarity.reverse_candidate_limit,
            exclude_game_id=game.id,
        )
        current = await similar.neighbor_slugs(game.id)
        candidates = _unique_slugs((*nearest, *current))
        if not candidates:
            return
        payload = SimilarityRecomputeRequested(
            run_id=run_id,
            process_date=process_date,
            scope="neighbors",
            center_slug=game.metacritic_slug,
            candidate_slugs=list(candidates),
            reason=reason,
        )
        event = build_cloud_event(
            self.settings,
            self.settings.similarity.subscribe_recompute_event,
            source=worker_source(self.settings, _WORKER_TYPE),
            subject=game.metacritic_slug,
            data=payload,
            stage="neighbors",
            run_id=run_id,
        )
        await OutboxRepository(session).insert(
            OutboxInsert(
                producer=_WORKER_TYPE,
                idempotency_key=event.idempotencykey,
                topic=self.settings.event_name(self.settings.similarity.subscribe_recompute_event),
                partition_key=game.metacritic_slug,
                payload=cloud_event_to_dict(event),
            )
        )

    async def _enqueue_assigned(
        self,
        session: AsyncSession,
        *,
        run_id: UUID | None,
        slug: str,
        items: list[SimilarGameRef],
    ) -> None:
        if run_id is None:
            return
        payload = GameSimilarAssigned(
            run_id=run_id,
            metacritic_slug=slug,
            items=items,
        )
        event = build_cloud_event(
            self.settings,
            self.settings.similarity.publish_event,
            source=worker_source(self.settings, _WORKER_TYPE),
            subject=slug,
            data=payload,
            stage=self.settings.similarity.stage_name,
            run_id=run_id,
        )
        await OutboxRepository(session).insert(
            OutboxInsert(
                producer=_WORKER_TYPE,
                idempotency_key=event.idempotencykey,
                topic=self.settings.event_name(self.settings.similarity.publish_event),
                partition_key=slug,
                payload=cloud_event_to_dict(event),
            )
        )

    async def _mark_item(
        self,
        session: AsyncSession,
        *,
        run_id: UUID | None,
        slug: str,
        process_date: date | None,
        event_id: str,
        status: IngestionItemStatus,
    ) -> None:
        if run_id is None or process_date is None:
            return
        await IngestionRepository(session).upsert_item(
            run_id=run_id,
            metacritic_slug=slug,
            process_date=process_date,
            stage=IngestionStage.similar,
            status=status,
            event_id=event_id,
        )

    async def _process_date(
        self,
        session: AsyncSession,
        run_id: UUID | None,
        explicit: date | None,
    ) -> date | None:
        if explicit is not None:
            return explicit
        if run_id is None:
            return None
        run = await IngestionRepository(session).get_run(run_id)
        return None if run is None else run.process_date


def _event_slug(data: Any) -> str | None:
    if isinstance(data, (GameCataloged, GameReviewsSummarized)):
        return data.metacritic_slug
    if isinstance(data, SimilarityRecomputeRequested):
        return data.center_slug
    return None


def _game_event_meta(
    data: Any,
) -> tuple[UUID | None, RecomputeReason, bool, date | None]:
    if isinstance(data, GameCataloged):
        return data.run_id, "cataloged", True, data.process_date
    if isinstance(data, GameReviewsSummarized):
        return data.run_id, "reviews", True, None
    if isinstance(data, SimilarityRecomputeRequested):
        return data.run_id, data.reason, False, data.process_date
    msg = "similarity unexpected game event payload"
    raise TypeError(msg)


def _require_in_corpus(corpus: Sequence[SimilarityGame], slug: str) -> SimilarityGame:
    for game in corpus:
        if game.metacritic_slug == slug:
            return game
    raise NotFoundError(f"game not found in corpus: {slug}")


def _unique_slugs(slugs: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for slug in slugs:
        if slug in seen:
            continue
        seen.add(slug)
        ordered.append(slug)
    return tuple(ordered)
