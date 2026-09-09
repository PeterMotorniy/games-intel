from __future__ import annotations

import json
from datetime import UTC, date, datetime
from uuid import UUID

from games_intel.contracts import GameCataloged, build_cloud_event
from games_intel.kafka.serialization import (
    CLOUDEVENTS_CONTENT_TYPE,
    cloud_event_headers,
    encode_cloud_event,
)
from games_intel.kafka.source import worker_source
from games_intel.kafka.testing import FakeBroker, FakeProducer
from games_intel.settings import Settings

RUN_ID = UUID("0191c0aa-7e3b-7000-8000-000000000001")
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _cataloged() -> GameCataloged:
    return GameCataloged.model_validate(
        {
            "run_id": RUN_ID,
            "process_date": date(2026, 9, 7),
            "metacritic_slug": "elden-ring",
            "title": "Elden Ring",
        }
    )


async def test_produce_uses_partition_key_and_cloudevents_header() -> None:
    settings = Settings()
    event = build_cloud_event(
        settings,
        "game_cataloged",
        source=worker_source(settings, "catalog"),
        subject="elden-ring",
        data=_cataloged(),
        stage="cataloged",
        run_id=RUN_ID,
        occurred_at=NOW,
    )
    broker = FakeBroker()
    producer = FakeProducer(broker)
    await producer.send(
        topic=event.type,
        key="elden-ring",
        value=encode_cloud_event(event),
        headers=cloud_event_headers(),
    )
    record = broker.topics[event.type][0]
    assert record.key == "elden-ring"
    assert record.headers == (("content-type", CLOUDEVENTS_CONTENT_TYPE.encode("utf-8")),)
    payload = json.loads(record.value.decode("utf-8"))
    assert payload["idempotencykey"]
    assert payload["type"] == settings.event_name("game_cataloged")
    assert UUID(payload["id"]).version == 7
