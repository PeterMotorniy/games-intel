from __future__ import annotations

from pydantic import SecretStr

from games_intel.kafka.client import admin_config, consumer_config, producer_config
from games_intel.settings import Settings


def test_sasl_settings_reach_client_config() -> None:
    settings = Settings()
    patched = settings.model_copy(
        update={
            "kafka": settings.kafka.model_copy(
                update={
                    "security_protocol": "SASL_PLAINTEXT",
                    "sasl_mechanism": "PLAIN",
                    "sasl_username": "kafka",
                    "sasl_password": SecretStr("secret"),
                }
            )
        }
    )
    producer = producer_config(patched, worker_type="catalog", instance_id="catalog-1")
    assert producer["security_protocol"] == "SASL_PLAINTEXT"
    assert producer["sasl_mechanism"] == "PLAIN"
    assert producer["sasl_plain_username"] == "kafka"
    assert producer["sasl_plain_password"] == "secret"
    admin = admin_config(patched, client_id="check")
    assert admin["sasl_plain_username"] == "kafka"
    assert admin["client_id"] == "check"


def test_consumer_enable_auto_commit_forced_false() -> None:
    settings = Settings()
    patched = settings.model_copy(
        update={"kafka": settings.kafka.model_copy(update={"enable_auto_commit": True})}
    )
    assert patched.kafka.enable_auto_commit is True
    cfg = consumer_config(
        patched,
        worker_type="catalog",
        instance_id="catalog-1",
        group_id=patched.consumer_group_id("catalog"),
    )
    assert cfg["enable_auto_commit"] is False
    assert cfg["max_poll_records"] == patched.kafka.max_poll_records
    assert cfg["max_poll_interval_ms"] == patched.kafka.max_poll_interval_ms
