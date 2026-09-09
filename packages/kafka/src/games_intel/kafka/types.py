from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TopicSpec:
    name: str
    event_key: str
    partitions: int
    replication_factor: int
    retention_ms: int
    kind: str


@dataclass(frozen=True, slots=True)
class IncomingRecord:
    topic: str
    partition: int
    offset: int
    key: str | None
    value: bytes
    headers: tuple[tuple[str, bytes], ...] = ()


class MessageProducer(Protocol):
    async def send(
        self,
        *,
        topic: str,
        key: str,
        value: bytes,
        headers: tuple[tuple[str, bytes], ...] = (),
    ) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


class MessageConsumer(Protocol):
    async def poll(self, timeout_seconds: float = 1.0) -> tuple[IncomingRecord, ...]: ...

    async def commit(self, record: IncomingRecord) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


def headers_map(headers: tuple[tuple[str, bytes], ...]) -> Mapping[str, bytes]:
    return {name: value for name, value in headers}
