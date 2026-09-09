from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from games_intel.kafka.client import admin_config
from games_intel.kafka.types import TopicSpec
from games_intel.settings import Settings, load_settings

GAME_EVENT_KEYS: frozenset[str] = frozenset(
    {
        "game_cataloged",
        "game_reviews_summarized",
        "game_letsplay_analyzed",
        "game_similar_assigned",
    }
)

CONTROL_EVENT_KEYS: frozenset[str] = frozenset(
    {
        "schedule_tick",
        "run_requested",
        "page_listed",
        "similarity_recompute",
        "worker_heartbeat",
        "dlq",
    }
)


def topic_specs(settings: Settings) -> tuple[TopicSpec, ...]:
    event_keys = tuple(type(settings.kafka.events).model_fields)
    known = GAME_EVENT_KEYS | CONTROL_EVENT_KEYS
    missing = known.difference(event_keys)
    extra = set(event_keys).difference(known)
    if missing or extra:
        msg = f"kafka.events keys mismatch known game/control sets: missing={missing} extra={extra}"
        raise ValueError(msg)
    retention_ms = settings.kafka.retention_hours * 3600 * 1000
    specs: list[TopicSpec] = []
    for event_key in event_keys:
        kind = "game" if event_key in GAME_EVENT_KEYS else "control"
        partitions = (
            settings.kafka.partitions.game_events
            if kind == "game"
            else settings.kafka.partitions.control
        )
        specs.append(
            TopicSpec(
                name=settings.event_name(event_key),
                event_key=event_key,
                partitions=partitions,
                replication_factor=settings.kafka.replication_factor,
                retention_ms=retention_ms,
                kind=kind,
            )
        )
    return tuple(specs)


def _topic_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("topic") or item.get("name") or "")
    return str(getattr(item, "topic", "") or getattr(item, "name", ""))


def _partition_count(item: Any) -> int:
    if isinstance(item, dict):
        partitions = item.get("partitions", [])
        return len(partitions)
    partitions = getattr(item, "partitions", [])
    return len(partitions)


async def ensure_topics(settings: Settings) -> tuple[str, ...]:
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic
    from aiokafka.errors import TopicAlreadyExistsError

    specs = topic_specs(settings)
    admin = AIOKafkaAdminClient(**admin_config(settings, client_id="games-intel-topics"))
    await admin.start()
    try:
        for spec in specs:
            topic = NewTopic(
                name=spec.name,
                num_partitions=spec.partitions,
                replication_factor=spec.replication_factor,
                topic_configs={"retention.ms": str(spec.retention_ms)},
            )
            try:
                await admin.create_topics([topic])
            except TopicAlreadyExistsError:
                continue
        return tuple(spec.name for spec in specs)
    finally:
        await admin.close()


async def check_topics(settings: Settings) -> list[str]:
    from aiokafka.admin import AIOKafkaAdminClient

    specs = topic_specs(settings)
    admin = AIOKafkaAdminClient(**admin_config(settings, client_id="games-intel-topics-check"))
    await admin.start()
    try:
        existing = {str(name) for name in await admin.list_topics()}
        problems: list[str] = []
        for spec in specs:
            if spec.name not in existing:
                problems.append(f"missing topic {spec.name}")
                continue
            if spec.kind == "game" and spec.partitions < 6:
                problems.append(
                    f"{spec.name} has {spec.partitions} partitions, expected >= 6 for game events"
                )
        described = await admin.describe_topics([spec.name for spec in specs])
        by_name: dict[str, Any] = {}
        for item in described:
            name = _topic_name(item)
            if name:
                by_name[name] = item
        for spec in specs:
            meta = by_name.get(spec.name)
            if meta is None:
                continue
            actual = _partition_count(meta)
            if actual != spec.partitions:
                problems.append(
                    f"{spec.name} partitions={actual}, expected {spec.partitions} from settings"
                )
        return problems
    finally:
        await admin.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or check Kafka topics from settings.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify topics exist with the configured partition counts.",
    )
    args = parser.parse_args(argv)
    settings = load_settings()
    if args.check:
        problems = asyncio.run(check_topics(settings))
        if problems:
            for problem in problems:
                print(problem, file=sys.stderr)
            return 1
        print("ok")
        return 0
    created = asyncio.run(ensure_topics(settings))
    for name in created:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
