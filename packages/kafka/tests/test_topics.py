from __future__ import annotations

import pytest

from games_intel.kafka.topics import topic_specs
from games_intel.settings import Settings, load_settings


def test_game_topics_have_at_least_six_partitions() -> None:
    specs = topic_specs(Settings())
    game = [spec for spec in specs if spec.kind == "game"]
    control = [spec for spec in specs if spec.kind == "control"]
    assert game
    assert control
    assert all(spec.partitions >= 6 for spec in game)
    assert {spec.event_key for spec in game} == {
        "game_cataloged",
        "game_reviews_summarized",
        "game_letsplay_analyzed",
        "game_similar_assigned",
    }
    assert "page_listed" in {spec.event_key for spec in control}


def test_topic_prefix_applied_to_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_CONFIG_PATH", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key in list(__import__("os").environ):
        if key.upper().startswith("GAMES_INTEL__"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GAMES_INTEL__KAFKA__TOPIC_PREFIX", "local.")
    settings = load_settings()
    names = {spec.name for spec in topic_specs(settings)}
    assert "local.games.page.listed" in names
    assert "local.ingestion.dlq" in names
    assert "games.page.listed" not in names
