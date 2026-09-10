from __future__ import annotations

from typing import Any

from games_intel.kafka.source import resolve_client_id
from games_intel.settings import Settings


def _security_kwargs(settings: Settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    protocol = settings.kafka.security_protocol.strip()
    if not protocol:
        return kwargs
    kwargs["security_protocol"] = protocol
    mechanism = settings.kafka.sasl_mechanism.strip()
    if mechanism:
        kwargs["sasl_mechanism"] = mechanism
    username = settings.kafka.sasl_username.strip()
    if username:
        kwargs["sasl_plain_username"] = username
    password = settings.kafka.sasl_password.get_secret_value()
    if password:
        kwargs["sasl_plain_password"] = password
    return kwargs


def admin_config(settings: Settings, *, client_id: str | None = None) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "bootstrap_servers": settings.kafka.bootstrap_servers,
    }
    if client_id:
        cfg["client_id"] = client_id
    cfg.update(_security_kwargs(settings))
    return cfg


def producer_config(
    settings: Settings,
    *,
    worker_type: str,
    instance_id: str,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "bootstrap_servers": settings.kafka.bootstrap_servers,
        "client_id": resolve_client_id(settings, worker_type, instance_id),
        "acks": "all",
        "request_timeout_ms": 20_000,
    }
    cfg.update(_security_kwargs(settings))
    return cfg


def consumer_config(
    settings: Settings,
    *,
    worker_type: str,
    instance_id: str,
    group_id: str,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "bootstrap_servers": settings.kafka.bootstrap_servers,
        "client_id": resolve_client_id(settings, worker_type, instance_id),
        "group_id": group_id,
        "enable_auto_commit": False,
        "auto_offset_reset": "earliest",
        "max_poll_records": settings.kafka.max_poll_records,
        "max_poll_interval_ms": settings.kafka.max_poll_interval_ms,
        "session_timeout_ms": settings.kafka.session_timeout_ms,
    }
    cfg.update(_security_kwargs(settings))
    return cfg
