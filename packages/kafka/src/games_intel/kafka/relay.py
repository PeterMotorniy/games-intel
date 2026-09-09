from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from games_intel.db.repositories.outbox import OutboxRepository
from games_intel.kafka.logging import emit_json
from games_intel.kafka.serialization import cloud_event_headers, encode_payload
from games_intel.kafka.types import MessageProducer

logger = logging.getLogger("games_intel.kafka.relay")

SleepFn = Callable[[float], Awaitable[None]]


class OutboxRelay:
    """Publish unpublished outbox rows. producer = worker_type, never instance_id."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        producer: MessageProducer,
        *,
        worker_type: str,
        batch_size: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._producer = producer
        self._worker_type = worker_type
        self._batch_size = batch_size

    async def publish_once(self) -> int:
        async with self._session_factory() as session:
            async with session.begin():
                claimed = await OutboxRepository(session).claim(
                    self._worker_type, limit=self._batch_size
                )
        published_ids: list[int] = []
        for row in claimed:
            try:
                await self._producer.send(
                    topic=row.topic,
                    key=row.partition_key,
                    value=encode_payload(row.payload),
                    headers=cloud_event_headers(),
                )
            except Exception as exc:
                emit_json(
                    logger,
                    level=logging.ERROR,
                    worker=self._worker_type,
                    outbox_id=row.id,
                    topic=row.topic,
                    error_type=type(exc).__name__,
                    event="outbox_produce_failed",
                )
                continue
            published_ids.append(row.id)
        if published_ids:
            async with self._session_factory() as session:
                async with session.begin():
                    await OutboxRepository(session).mark_published(published_ids)
        return len(published_ids)

    async def run_loop(
        self,
        stop: asyncio.Event,
        sleep: SleepFn,
        *,
        interval_seconds: float = 0.5,
    ) -> None:
        while not stop.is_set():
            try:
                await self.publish_once()
            except Exception as exc:
                emit_json(
                    logger,
                    level=logging.ERROR,
                    worker=self._worker_type,
                    error_type=type(exc).__name__,
                    event="outbox_relay_failed",
                )
            await sleep(interval_seconds)
