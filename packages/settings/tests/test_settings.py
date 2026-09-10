from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from games_intel.settings import Settings, WorkerSliceSettings, load_settings

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_YAML = REPO_ROOT / "config.example.yaml"


def _clear_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_CONFIG_PATH", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key in list(__import__("os").environ):
        if key.upper().startswith("GAMES_INTEL__"):
            monkeypatch.delenv(key, raising=False)


def _key_paths(payload: Mapping[str, Any], prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()
    for key, value in payload.items():
        path = (*prefix, str(key))
        paths.add(path)
        if isinstance(value, Mapping):
            paths.update(_key_paths(value, path))
    return paths


def _settings_dump(settings: Settings) -> dict[str, Any]:
    return settings.model_dump(mode="python")


def test_example_yaml_key_snapshot_matches_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    monkeypatch.setenv("APP_CONFIG_PATH", str(EXAMPLE_YAML))
    loaded = load_settings()
    raw = yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    assert _key_paths(raw) == _key_paths(_settings_dump(loaded))


def test_unknown_key_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear_overlay(monkeypatch)
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("app:\n  name: x\n  not_a_real_key: 1\n", encoding="utf-8")
    monkeypatch.setenv("APP_CONFIG_PATH", str(cfg))
    with pytest.raises(ValidationError):
        load_settings()


def test_env_overlay_overrides_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    monkeypatch.setenv("APP_CONFIG_PATH", str(EXAMPLE_YAML))
    monkeypatch.setenv("GAMES_INTEL__APP__LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("GAMES_INTEL__SCHEDULER__DEFAULT_LIMIT", "7")
    loaded = load_settings()
    assert loaded.app.log_level == "DEBUG"
    assert loaded.scheduler.default_limit == 7


def test_enable_auto_commit_default_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    loaded = Settings()
    assert loaded.kafka.enable_auto_commit is False


def test_architecture_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    loaded = Settings()
    assert loaded.scheduler.tick_cron == "0 * * * *"
    assert loaded.scheduler.default_limit == 20
    assert loaded.discovery.browse_list_limit == 48
    assert loaded.kafka.partitions.game_events == 6
    assert loaded.idempotency.key_template == "{event_type}:{run_id}:{subject}:{stage}"
    assert loaded.adapters.youtube.min_duration_seconds == 180
    assert loaded.adapters.youtube.max_duration_seconds == 7200
    assert loaded.adapters.youtube.exclude_title_patterns == ["compilation", "top 10"]
    assert loaded.letsplay.stt_enabled is True
    assert loaded.stt.enabled is True
    assert loaded.stt.model == "whisper-1"
    assert loaded.stt.base_url == "https://api.openai.com/v1"
    assert loaded.stt.timeout_seconds == 120
    assert loaded.llm.model == "google/gemini-2.5-flash-lite"
    assert loaded.llm.base_url == "https://openrouter.ai/api/v1"
    assert loaded.llm.api_key.get_secret_value() == ""
    assert loaded.llm.timeout_seconds == 60
    assert loaded.llm.max_tokens == 512
    assert loaded.embeddings.model == "openai/text-embedding-3-small"
    assert loaded.embeddings.base_url == "https://openrouter.ai/api/v1"
    assert loaded.embeddings.vector_dim == 768
    assert loaded.monitor.heartbeat_stale_seconds == 30
    assert loaded.monitor.sse_poll_seconds == 2.0
    event_fields = set(type(loaded.kafka.events).model_fields)
    assert event_fields == {
        "schedule_tick",
        "run_requested",
        "page_listed",
        "game_listed",
        "game_cataloged",
        "game_reviews_summarized",
        "game_letsplay_analyzed",
        "game_similar_assigned",
        "similarity_recompute",
        "worker_heartbeat",
        "dlq",
    }
    group_fields = set(type(loaded.kafka.consumer_groups).model_fields)
    assert group_fields == {
        "scheduler",
        "discovery",
        "catalog",
        "reviews",
        "letsplay",
        "similarity",
    }


def test_replica_group_antipattern_is_not_configurable() -> None:
    """Different consumer_groups per replica would deliver every message twice.

    Architecture forbids a per-replica group field; this is the documented anti-test.
    """
    replica_unique = set(WorkerSliceSettings.model_fields) & {
        "consumer_group_id",
        "unique_group",
        "replica_group",
        "group_id",
    }
    assert replica_unique == set()
    loaded = Settings()
    replica_a = loaded.consumer_group_id(loaded.catalog.consumer_group)
    replica_b = loaded.consumer_group_id(loaded.catalog.consumer_group)
    assert replica_a == replica_b == "games-intel.catalog"


def test_instance_id_comes_from_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    monkeypatch.setenv("HOSTNAME", "catalog-replica-a")
    loaded = Settings()
    assert loaded.catalog.instance_id == "catalog-replica-a"
    assert loaded.reviews.instance_id == "catalog-replica-a"


def test_workers_read_topics_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    loaded = Settings()
    assert loaded.discovery.publish_event == "game_listed"
    assert loaded.event_name(loaded.discovery.publish_event) == "game.listed"
    assert loaded.event_name(loaded.catalog.subscribe_event) == "game.listed"
    assert loaded.event_name(loaded.reviews.subscribe_event) == "game.cataloged"
    assert loaded.event_name(loaded.letsplay.subscribe_event) == "game.cataloged"


def test_topic_prefix_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    monkeypatch.setenv("GAMES_INTEL__KAFKA__TOPIC_PREFIX", "local.")
    loaded = Settings()
    assert loaded.event_name("page_listed") == "local.games.page.listed"


def test_openai_api_key_shared_from_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    monkeypatch.setenv("GAMES_INTEL__LLM__API_KEY", "sk-shared-test")
    loaded = Settings()
    assert loaded.llm.api_key.get_secret_value() == "sk-shared-test"
    assert loaded.embeddings.api_key.get_secret_value() == "sk-shared-test"
    assert loaded.stt.api_key.get_secret_value() == ""


def test_stt_inherits_llm_key_only_on_same_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    monkeypatch.setenv("GAMES_INTEL__LLM__API_KEY", "sk-shared-test")
    monkeypatch.setenv("GAMES_INTEL__STT__BASE_URL", "https://openrouter.ai/api/v1")
    loaded = Settings()
    assert loaded.stt.api_key.get_secret_value() == "sk-shared-test"


def test_database_url_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_overlay(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/games")
    loaded = load_settings()
    assert loaded.database.url.get_secret_value() == "postgresql://user:pass@localhost/games"


def test_process_date_uses_configured_timezone() -> None:
    from datetime import UTC, date, datetime

    from games_intel.settings.clock import process_date_for

    settings = Settings().model_copy(
        update={"app": Settings().app.model_copy(update={"process_timezone": "America/New_York"})}
    )
    when = datetime(2026, 9, 8, 2, 30, tzinfo=UTC)
    assert process_date_for(settings, when) == date(2026, 9, 7)
