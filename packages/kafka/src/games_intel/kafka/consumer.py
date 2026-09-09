from __future__ import annotations

from typing import Any

from games_intel.kafka.client import consumer_config
from games_intel.kafka.types import IncomingRecord
from games_intel.settings import Settings


def _decode_key(key: bytes | None) -> str | None:
    if key is None:
        return None
    return key.decode("utf-8")


def _decode_headers(headers: Any) -> tuple[tuple[str, bytes], ...]:
    if not headers:
        return ()
    decoded: list[tuple[str, bytes]] = []
    for name, value in headers:
        header_name = name if isinstance(name, str) else name.decode("utf-8")
        header_value = value if isinstance(value, bytes) else b""
        decoded.append((header_name, header_value))
    return tuple(decoded)


class KafkaConsumer:
    def __init__(
        self,
        settings: Settings,
        *,
        worker_type: str,
        instance_id: str,
        group_id: str,
        topics: tuple[str, ...],
    ) -> None:
        self._config = consumer_config(
            settings,
            worker_type=worker_type,
            instance_id=instance_id,
            group_id=group_id,
        )
        self._topics = topics
        self._consumer: Any = None

    @property
    def enable_auto_commit(self) -> bool:
        return bool(self._config["enable_auto_commit"])

    async def start(self) -> None:
        from aiokafka import AIOKafkaConsumer

        self._consumer = AIOKafkaConsumer(*self._topics, **self._config)
        await self._consumer.start()

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def poll(self, timeout_seconds: float = 1.0) -> tuple[IncomingRecord, ...]:
        if self._consumer is None:
            msg = "consumer is not started"
            raise RuntimeError(msg)
        batches = await self._consumer.getmany(
            timeout_ms=int(timeout_seconds * 1000),
            max_records=self._config["max_poll_records"],
        )
        records: list[IncomingRecord] = []
        for messages in batches.values():
            for message in messages:
                records.append(
                    IncomingRecord(
                        topic=message.topic,
                        partition=message.partition,
                        offset=message.offset,
                        key=_decode_key(message.key),
                        value=message.value if message.value is not None else b"",
                        headers=_decode_headers(message.headers),
                    )
                )
        return tuple(records)

    async def commit(self, record: IncomingRecord) -> None:
        if self._consumer is None:
            msg = "consumer is not started"
            raise RuntimeError(msg)
        from aiokafka import TopicPartition
        from aiokafka.structs import OffsetAndMetadata

        tp = TopicPartition(record.topic, record.partition)
        await self._consumer.commit({tp: OffsetAndMetadata(record.offset + 1, "")})
