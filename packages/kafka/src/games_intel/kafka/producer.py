from __future__ import annotations

import asyncio
from typing import Any

from games_intel.kafka.client import producer_config
from games_intel.kafka.serialization import cloud_event_headers
from games_intel.settings import Settings

_SEND_TIMEOUT_SECONDS = 20.0


class KafkaProducer:
    def __init__(self, settings: Settings, *, worker_type: str, instance_id: str) -> None:
        self._config = producer_config(settings, worker_type=worker_type, instance_id=instance_id)
        self._producer: Any = None

    async def start(self) -> None:
        from aiokafka import AIOKafkaProducer

        self._producer = AIOKafkaProducer(**self._config)
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def send(
        self,
        *,
        topic: str,
        key: str,
        value: bytes,
        headers: tuple[tuple[str, bytes], ...] = (),
    ) -> None:
        if self._producer is None:
            msg = "producer is not started"
            raise RuntimeError(msg)
        send_headers = headers or cloud_event_headers()
        await asyncio.wait_for(
            self._producer.send_and_wait(
                topic,
                value=value,
                key=key.encode("utf-8"),
                headers=list(send_headers),
            ),
            timeout=_SEND_TIMEOUT_SECONDS,
        )
