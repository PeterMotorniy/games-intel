from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = REPO_ROOT / "infra/compose/compose.yaml"
COMPOSE_PROD = REPO_ROOT / "infra/compose/compose.prod.yaml"
DOCKERFILE_APP = REPO_ROOT / "infra/compose/Dockerfile.app"
EXAMPLE_YAML = REPO_ROOT / "config.example.yaml"

DAEMON_PACKAGES = {
    "games-intel-scheduler",
    "games-intel-discovery",
    "games-intel-catalog",
    "games-intel-similarity",
    "games-intel-api",
    "games-intel-db",
}
AGENT_PACKAGES = {"games-intel-reviews", "games-intel-letsplay"}


def _load_compose() -> dict[str, Any]:
    loaded = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _services() -> dict[str, dict[str, Any]]:
    services = _load_compose()["services"]
    assert isinstance(services, dict)
    typed: dict[str, dict[str, Any]] = {}
    for name, spec in services.items():
        assert isinstance(name, str)
        assert isinstance(spec, dict)
        typed[name] = cast(dict[str, Any], spec)
    return typed


def _mapping(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_compose_has_required_services() -> None:
    names = set(_services())
    required = {
        "postgres",
        "kafka",
        "kafka-init",
        "migrate",
        "scrape-metacritic",
        "scheduler",
        "tick",
        "discovery",
        "catalog",
        "catalog-replica",
        "reviews",
        "letsplay",
        "similarity",
        "api",
        "web",
    }
    assert required <= names
    loaded = _load_compose()
    assert loaded.get("name") == "games-intel"


def test_compose_tick_source_external_and_one_cron() -> None:
    example = yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))
    assert example["scheduler"]["tick_source"] == "external"
    services = _services()
    command = services["tick"]["command"]
    assert isinstance(command, list)
    assert "external_tick" in " ".join(str(part) for part in command)
    env = _mapping(services["scheduler"]["environment"])
    assert env["GAMES_INTEL__SCHEDULER__TICK_SOURCE"] == "external"


def test_compose_auto_migrate_false() -> None:
    services = _services()
    api_env = _mapping(services["api"]["environment"])
    assert api_env["GAMES_INTEL__DATABASE__AUTO_MIGRATE"] == "false"
    prod = yaml.safe_load(COMPOSE_PROD.read_text(encoding="utf-8"))
    prod_text = COMPOSE_PROD.read_text(encoding="utf-8")
    assert 'GAMES_INTEL__DATABASE__AUTO_MIGRATE: "false"' in prod_text
    prod_api = _mapping(_mapping(prod["services"])["api"])
    assert _mapping(prod_api["environment"])["GAMES_INTEL__DATABASE__AUTO_MIGRATE"] == "false"


def test_compose_kafka_client_listeners_use_sasl() -> None:
    kafka = _mapping(_services()["kafka"]["environment"])
    protocol_map = str(kafka["KAFKA_LISTENER_SECURITY_PROTOCOL_MAP"])
    assert "BROKER:SASL_PLAINTEXT" in protocol_map
    assert "HOST:SASL_PLAINTEXT" in protocol_map
    assert "kafka-healthcheck.sh" in str(_services()["kafka"]["healthcheck"])
    healthcheck_script = REPO_ROOT / "infra/compose/kafka-healthcheck.sh"
    assert healthcheck_script.is_file()
    assert b"\r" not in healthcheck_script.read_bytes()
    init_env = _mapping(_services()["kafka-init"]["environment"])
    assert "GAMES_INTEL__KAFKA__SASL_PASSWORD" in init_env
    app_env = _mapping(_services()["scheduler"]["environment"])
    assert app_env["GAMES_INTEL__KAFKA__SECURITY_PROTOCOL"].startswith("${")
    assert "SASL_PLAINTEXT" in app_env["GAMES_INTEL__KAFKA__SECURITY_PROTOCOL"]


def test_sidecar_not_published() -> None:
    scrape = _services()["scrape-metacritic"]
    assert "ports" not in scrape
    assert scrape.get("expose") == ["8080"]


def test_catalog_replicas_share_group_and_use_hostname() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "GAMES_INTEL__CATALOG__INSTANCE_ID" not in text
    assert "GAMES_INTEL__KAFKA__CONSUMER_GROUPS__CATALOG" not in text
    services = _services()
    assert "deploy" not in services["catalog"]
    assert "catalog-replica" in services
    example = yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))
    partitions = int(example["kafka"]["partitions"]["game_events"])
    assert partitions >= 2


def test_example_yaml_metacritic_markers_cover_odyssey() -> None:
    example = yaml.safe_load(EXAMPLE_YAML.read_text(encoding="utf-8"))
    meta = example["adapters"]["metacritic"]
    assert "product-hero" in meta["markers"]["card_container"]
    assert "new-game-release-carousel" in meta["markers"]["listing_container"]
    assert "filter-results" not in meta["markers"]["listing_container"]
    assert "filter-results" in meta["markers"]["browse_listing_container"]


def test_daemon_images_do_not_install_langchain() -> None:
    dockerfile = DOCKERFILE_APP.read_text(encoding="utf-8")
    assert "EXPECT_LANGCHAIN" in dockerfile
    assert "find_spec('langchain')" in dockerfile
    services = _services()
    for name in ("scheduler", "discovery", "catalog", "catalog-replica", "similarity", "api"):
        args = _mapping(_mapping(services[name]["build"])["args"])
        assert args["EXPECT_LANGCHAIN"] == "0"
        assert args["PACKAGE"] in DAEMON_PACKAGES or name in {"catalog", "catalog-replica"}
    reviews_args = _mapping(_mapping(services["reviews"]["build"])["args"])
    letsplay_args = _mapping(_mapping(services["letsplay"]["build"])["args"])
    assert reviews_args["EXPECT_LANGCHAIN"] == "1"
    assert letsplay_args["EXPECT_LANGCHAIN"] == "1"
    assert reviews_args["PACKAGE"] in AGENT_PACKAGES
    assert letsplay_args["PACKAGE"] in AGENT_PACKAGES


def test_web_does_not_cache_monitor() -> None:
    nginx = (REPO_ROOT / "infra/compose/nginx.conf").read_text(encoding="utf-8")
    assert "/api/v1/monitor" in nginx
    assert "no-store" in nginx
    assert "proxy_buffering off" in nginx


def test_healthchecks_present() -> None:
    services = _services()
    assert "healthcheck" in services["postgres"]
    assert "healthcheck" in services["kafka"]
    assert "healthcheck" in services["scrape-metacritic"]
    assert "/healthz" in str(services["scrape-metacritic"]["healthcheck"])
    assert "healthcheck" in services["api"]
    assert "/readyz" in str(services["api"]["healthcheck"])


def test_postgres_and_kafka_restart_unless_stopped() -> None:
    services = _services()
    assert services["postgres"]["restart"] == "unless-stopped"
    assert services["kafka"]["restart"] == "unless-stopped"
    assert "kafka_data" in str(services["kafka"].get("volumes", []))


def test_workers_wait_for_postgres_and_kafka() -> None:
    services = _services()
    for name in (
        "scheduler",
        "discovery",
        "catalog",
        "reviews",
        "letsplay",
        "similarity",
        "api",
        "tick",
    ):
        depends = _mapping(services[name]["depends_on"])
        assert depends["postgres"]["condition"] == "service_healthy"
        assert depends["kafka"]["condition"] == "service_healthy"
