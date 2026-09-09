from __future__ import annotations

from collections import defaultdict

from games_intel.kafka.types import IncomingRecord


class ProduceError(Exception):
    """Fake broker produce failure."""


class FakeBroker:
    def __init__(self) -> None:
        self.topics: dict[str, list[IncomingRecord]] = defaultdict(list)
        self.fail_produce = False

    def append(
        self,
        *,
        topic: str,
        key: str,
        value: bytes,
        headers: tuple[tuple[str, bytes], ...] = (),
    ) -> IncomingRecord:
        if self.fail_produce:
            raise ProduceError("fake broker produce failed")
        offset = len(self.topics[topic])
        record = IncomingRecord(
            topic=topic,
            partition=0,
            offset=offset,
            key=key,
            value=value,
            headers=headers,
        )
        self.topics[topic].append(record)
        return record


class FakeProducer:
    def __init__(self, broker: FakeBroker) -> None:
        self.broker = broker
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def send(
        self,
        *,
        topic: str,
        key: str,
        value: bytes,
        headers: tuple[tuple[str, bytes], ...] = (),
    ) -> None:
        self.broker.append(topic=topic, key=key, value=value, headers=headers)


class FakeConsumer:
    def __init__(
        self,
        broker: FakeBroker,
        topics: tuple[str, ...],
        *,
        fail_commit_times: int = 0,
    ) -> None:
        self.broker = broker
        self.topics = topics
        self.committed: dict[tuple[str, int], int] = {}
        self._positions: dict[str, int] = {topic: 0 for topic in topics}
        self.started = False
        self.fail_commit_times = fail_commit_times

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def poll(self, timeout_seconds: float = 1.0) -> tuple[IncomingRecord, ...]:
        del timeout_seconds
        records: list[IncomingRecord] = []
        for topic in self.topics:
            log = self.broker.topics[topic]
            position = self._positions[topic]
            if position < len(log):
                record = log[position]
                self._positions[topic] = position + 1
                records.append(record)
        return tuple(records)

    async def commit(self, record: IncomingRecord) -> None:
        if self.fail_commit_times > 0:
            self.fail_commit_times -= 1
            msg = "killed after persist before offset commit"
            raise RuntimeError(msg)
        self.committed[(record.topic, record.partition)] = record.offset + 1
