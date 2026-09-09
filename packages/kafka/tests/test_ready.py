from __future__ import annotations

import pytest
from pydantic import SecretStr

from games_intel.kafka.ready import is_kafka_ready, wait_until_backend_ready
from games_intel.settings import Settings


async def test_is_kafka_ready_empty_bootstrap() -> None:
    base = Settings()
    settings = base.model_copy(
        update={"kafka": base.kafka.model_copy(update={"bootstrap_servers": ""})}
    )
    assert await is_kafka_ready(settings) is False


async def test_is_kafka_ready_passes_sasl_to_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeAdmin:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        async def start(self) -> None:
            return None

        async def list_topics(self) -> list[str]:
            return []

        async def close(self) -> None:
            return None

    monkeypatch.setattr("aiokafka.admin.AIOKafkaAdminClient", FakeAdmin)
    base = Settings()
    settings = base.model_copy(
        update={
            "kafka": base.kafka.model_copy(
                update={
                    "bootstrap_servers": "kafka:29092",
                    "security_protocol": "SASL_PLAINTEXT",
                    "sasl_mechanism": "PLAIN",
                    "sasl_username": "kafka",
                    "sasl_password": SecretStr("secret"),
                }
            )
        }
    )
    assert await is_kafka_ready(settings) is True
    assert captured["security_protocol"] == "SASL_PLAINTEXT"
    assert captured["sasl_plain_username"] == "kafka"
    assert captured["sasl_plain_password"] == "secret"


async def test_wait_until_backend_ready_retries_then_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    db_calls = {"n": 0}

    async def fake_db(_engine: object) -> bool:
        db_calls["n"] += 1
        return db_calls["n"] >= 2

    async def fake_kafka(_settings: Settings) -> bool:
        return True

    monkeypatch.setattr("games_intel.kafka.ready.is_database_ready", fake_db)
    monkeypatch.setattr("games_intel.kafka.ready.is_kafka_ready", fake_kafka)
    ok = await wait_until_backend_ready(
        engine=object(),  # type: ignore[arg-type]
        settings=settings,
        sleep=fake_sleep,
        attempts=3,
        interval_seconds=0.01,
    )
    assert ok is True
    assert sleeps == [0.01]
    assert db_calls["n"] == 2


async def test_wait_until_backend_ready_skips_kafka_when_not_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    async def fake_db(_engine: object) -> bool:
        return True

    async def fake_kafka(_settings: Settings) -> bool:
        raise AssertionError("kafka must not be probed")

    monkeypatch.setattr("games_intel.kafka.ready.is_database_ready", fake_db)
    monkeypatch.setattr("games_intel.kafka.ready.is_kafka_ready", fake_kafka)
    ok = await wait_until_backend_ready(
        engine=object(),  # type: ignore[arg-type]
        settings=settings,
        sleep=fake_sleep,
        attempts=1,
        require_kafka=False,
    )
    assert ok is True
    assert sleeps == []
