from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from games_intel.adapters.youtube.audio import cleanup_downloaded_audio
from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.adapters.youtube.port import YouTubePort
from games_intel.agents.letsplay_analyst.exceptions import (
    LlmStructureError as AgentLlmStructureError,
)
from games_intel.agents.letsplay_analyst.exceptions import LlmTransientError
from games_intel.agents.letsplay_analyst.port import LetsPlayAnalystAgent
from games_intel.agents.transcription.exceptions import SttFailedError
from games_intel.agents.transcription.port import TranscriptionAgent
from games_intel.contracts.adapters import (
    GetAudioInput,
    GetTranscriptInput,
    SearchLetsPlaysInput,
    VideoHit,
)
from games_intel.contracts.agents import (
    LetsPlayAnalystInput,
    LetsPlayConclusion,
    TranscriptionInput,
)
from games_intel.contracts.builder import build_cloud_event
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.ids import new_traceparent
from games_intel.contracts.payloads import GameCataloged, GameLetsPlayAnalyzed, LetsPlayStatus
from games_intel.db.exceptions import GameNotFoundError
from games_intel.db.records import LetsPlaySlice, OutboxInsert
from games_intel.db.repositories.ingestion import IngestionRepository
from games_intel.db.repositories.letsplay import GameLetsPlayRepository
from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.db.types import IngestionItemStatus, IngestionStage
from games_intel.db.types import LetsPlayStatus as DbLetsPlayStatus
from games_intel.kafka.classify import map_adapter_error
from games_intel.kafka.exceptions import (
    LlmStructureError,
    NotFoundError,
    QuotaError,
    TransientError,
)
from games_intel.kafka.logging import emit_json
from games_intel.kafka.serialization import cloud_event_to_dict
from games_intel.kafka.source import worker_source
from games_intel.settings import Settings

logger = logging.getLogger("games_intel.workers.letsplay")

_WORKER_TYPE = "letsplay"


@dataclass(frozen=True, slots=True)
class _LetsPlayPrepared:
    discovered: GameCataloged
    status: LetsPlayStatus
    item_status: IngestionItemStatus
    hit: VideoHit | None
    conclusion: LetsPlayConclusion | None


class LetsPlayHandler:
    """YouTube Port + optional STT/analyst. Worker clips transcript before analyst."""

    def __init__(
        self,
        settings: Settings,
        youtube: YouTubePort,
        transcription: TranscriptionAgent,
        analyst: LetsPlayAnalystAgent,
    ) -> None:
        self.settings = settings
        self.youtube = youtube
        self.transcription = transcription
        self.analyst = analyst

    async def prepare(self, event: CloudEvent[Any]) -> _LetsPlayPrepared:
        discovered = event.data
        if not isinstance(discovered, GameCataloged):
            msg = "letsplay expected GameCataloged payload"
            raise TypeError(msg)
        hit: VideoHit | None = None
        text: str | None = None
        try:
            hit = await self._search(discovered)
            if hit is None:
                return _LetsPlayPrepared(
                    discovered=discovered,
                    status="no_video",
                    item_status=IngestionItemStatus.degraded,
                    hit=None,
                    conclusion=None,
                )
            text = await self._resolve_transcript(discovered, hit)
        except QuotaError:
            return _LetsPlayPrepared(
                discovered=discovered,
                status="quota_exceeded",
                item_status=IngestionItemStatus.degraded,
                hit=hit,
                conclusion=None,
            )
        if text is None:
            return _LetsPlayPrepared(
                discovered=discovered,
                status="transcript_unavailable",
                item_status=IngestionItemStatus.degraded,
                hit=hit,
                conclusion=None,
            )
        excerpt = clip_transcript(text, self.settings.letsplay.transcript_max_chars)
        assert hit is not None
        try:
            conclusion = await self.analyst.ainvoke(
                LetsPlayAnalystInput(
                    run_id=discovered.run_id,
                    metacritic_slug=discovered.metacritic_slug,
                    video_title=hit.title,
                    transcript_excerpt=excerpt,
                )
            )
        except AgentLlmStructureError as exc:
            raise LlmStructureError(str(exc)) from exc
        except LlmTransientError as exc:
            raise TransientError(str(exc)) from exc
        return _LetsPlayPrepared(
            discovered=discovered,
            status="ok",
            item_status=IngestionItemStatus.completed,
            hit=hit,
            conclusion=conclusion,
        )

    async def persist(
        self, event: CloudEvent[Any], session: AsyncSession, prepared: _LetsPlayPrepared
    ) -> None:
        await self._persist(
            session,
            event,
            prepared.discovered,
            status=prepared.status,
            item_status=prepared.item_status,
            hit=prepared.hit,
            conclusion=prepared.conclusion,
        )

    async def handle(self, event: CloudEvent[Any], session: AsyncSession) -> None:
        prepared = await self.prepare(event)
        await self.persist(event, session, prepared)

    async def _search(self, discovered: GameCataloged) -> VideoHit | None:
        try:
            result = await self.youtube.search_letsplays(
                SearchLetsPlaysInput(
                    title=discovered.title,
                    max_results=self.settings.letsplay.search_max_results,
                )
            )
        except YoutubeAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc
        if not result.items:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=discovered.metacritic_slug,
                worker=_WORKER_TYPE,
                stage=self.settings.letsplay.stage_name,
                event="letsplay_no_video",
                run_id=str(discovered.run_id),
            )
            return None
        return result.items[0]

    async def _resolve_transcript(self, discovered: GameCataloged, hit: VideoHit) -> str | None:
        max_chars = self.settings.letsplay.transcript_max_chars
        try:
            transcript = await self.youtube.get_transcript(
                GetTranscriptInput(video_id=hit.video_id, max_chars=max_chars)
            )
        except YoutubeAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc
        if transcript.status == "ok" and transcript.text.strip():
            return transcript.text
        if not self.settings.letsplay.stt_enabled:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=discovered.metacritic_slug,
                worker=_WORKER_TYPE,
                stage=self.settings.letsplay.stage_name,
                event="letsplay_transcript_unavailable",
                run_id=str(discovered.run_id),
            )
            return None
        try:
            audio = await self.youtube.get_audio(
                GetAudioInput(
                    video_id=hit.video_id,
                    max_duration_seconds=self.settings.letsplay.max_video_duration_seconds,
                )
            )
        except YoutubeAdapterError as exc:
            raise map_adapter_error(exc.to_dto()) from exc
        if audio.status != "ok" or not audio.audio_ref:
            return None
        try:
            spoken = await self.transcription.ainvoke(
                TranscriptionInput(
                    run_id=discovered.run_id,
                    metacritic_slug=discovered.metacritic_slug,
                    audio_ref=audio.audio_ref,
                )
            )
        except SttFailedError:
            emit_json(
                logger,
                level=logging.WARNING,
                slug=discovered.metacritic_slug,
                worker=_WORKER_TYPE,
                stage=self.settings.letsplay.stage_name,
                event="letsplay_stt_failed",
                run_id=str(discovered.run_id),
            )
            return None
        finally:
            cleanup_downloaded_audio(audio.audio_ref)
        if not spoken.text.strip():
            return None
        return spoken.text

    async def _persist(
        self,
        session: AsyncSession,
        event: CloudEvent[Any],
        discovered: GameCataloged,
        *,
        status: LetsPlayStatus,
        item_status: IngestionItemStatus,
        hit: VideoHit | None = None,
        conclusion: LetsPlayConclusion | None = None,
    ) -> None:
        video_url = None if hit is None else str(hit.url)
        video_title = None if hit is None else hit.title
        view_count = None if hit is None else hit.view_count
        conclusion_text = None if conclusion is None else conclusion.conclusion
        highlights = None if conclusion is None else tuple(conclusion.highlights)
        try:
            game_id = await GameLetsPlayRepository(session).update_letsplay(
                LetsPlaySlice(
                    metacritic_slug=discovered.metacritic_slug,
                    status=DbLetsPlayStatus(status),
                    video_url=video_url,
                    video_title=video_title,
                    view_count=view_count,
                    conclusion=conclusion_text,
                    highlights=highlights,
                )
            )
        except GameNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        await IngestionRepository(session).upsert_item(
            run_id=discovered.run_id,
            metacritic_slug=discovered.metacritic_slug,
            process_date=discovered.process_date,
            stage=IngestionStage.letsplay,
            status=item_status,
            game_id=game_id,
            event_id=event.id,
        )
        payload = GameLetsPlayAnalyzed(
            run_id=discovered.run_id,
            metacritic_slug=discovered.metacritic_slug,
            status=status,
            video_url=None if hit is None else hit.url,
            video_title=video_title,
            view_count=view_count,
            conclusion=conclusion_text,
            highlights=[] if highlights is None else list(highlights),
        )
        outbox_event = build_cloud_event(
            self.settings,
            self.settings.letsplay.publish_event,
            source=worker_source(self.settings, _WORKER_TYPE),
            subject=discovered.metacritic_slug,
            data=payload,
            stage=self.settings.letsplay.stage_name,
            run_id=discovered.run_id,
            traceparent=new_traceparent(),
        )
        await OutboxRepository(session).insert(
            OutboxInsert(
                producer=_WORKER_TYPE,
                idempotency_key=outbox_event.idempotencykey,
                topic=self.settings.event_name(self.settings.letsplay.publish_event),
                partition_key=discovered.metacritic_slug,
                payload=cloud_event_to_dict(outbox_event),
            )
        )


def clip_transcript(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
