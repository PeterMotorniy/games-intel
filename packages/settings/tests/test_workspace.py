from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PURE_DAEMON_PYPROJECTS = (
    REPO_ROOT / "apps/workers/scheduler/pyproject.toml",
    REPO_ROOT / "apps/workers/discovery/pyproject.toml",
    REPO_ROOT / "apps/workers/catalog/pyproject.toml",
    REPO_ROOT / "apps/workers/similarity/pyproject.toml",
    REPO_ROOT / "pyproject.toml",
)


def test_pure_daemons_do_not_depend_on_langchain() -> None:
    for path in PURE_DAEMON_PYPROJECTS:
        text = path.read_text(encoding="utf-8").lower()
        assert "langchain" not in text
        assert "langgraph" not in text


def test_example_env_has_empty_secrets() -> None:
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in env_example
    assert "sk-" not in env_example
    yaml_text = (REPO_ROOT / "config.example.yaml").read_text(encoding="utf-8")
    loaded = yaml.safe_load(yaml_text)
    assert loaded["database"]["url"] == ""
    assert loaded["llm"]["api_key"] == ""
    assert loaded["embeddings"]["api_key"] == ""
    assert loaded["stt"]["api_key"] == ""
    assert "langsmith" not in loaded
    assert "deepgram" not in loaded["stt"]
    assert "assemblyai" not in loaded["stt"]
    assert "faster_whisper" not in loaded["stt"]
    assert loaded["adapters"]["youtube"]["api_key"] == ""


def test_stub_packages_import() -> None:
    import games_intel.adapters.embeddings  # noqa: F401
    import games_intel.adapters.media  # noqa: F401
    import games_intel.adapters.metacritic  # noqa: F401
    import games_intel.adapters.stt  # noqa: F401
    import games_intel.adapters.youtube  # noqa: F401
    import games_intel.agents.review_summarizer  # noqa: F401
    import games_intel.api  # noqa: F401
    import games_intel.contracts  # noqa: F401
    import games_intel.db  # noqa: F401
    import games_intel.kafka  # noqa: F401
    import games_intel.scrape.metacritic  # noqa: F401
    import games_intel.settings  # noqa: F401
    import games_intel.workers.catalog  # noqa: F401
    import games_intel.workers.discovery  # noqa: F401
    import games_intel.workers.reviews  # noqa: F401
    import games_intel.workers.scheduler  # noqa: F401
    import games_intel.workers.similarity  # noqa: F401


def test_api_does_not_depend_on_langchain() -> None:
    text = (REPO_ROOT / "apps/api/pyproject.toml").read_text().lower()
    assert "langchain" not in text
    assert "langgraph" not in text
    agent = (REPO_ROOT / "packages/agents/review_summarizer/pyproject.toml").read_text().lower()
    reviews = (REPO_ROOT / "apps/workers/reviews/pyproject.toml").read_text().lower()
    scheduler = (REPO_ROOT / "apps/workers/scheduler/pyproject.toml").read_text().lower()
    assert "langchain" in agent
    assert "langgraph" in agent
    assert "langgraph-checkpoint-postgres" in agent
    assert "langchain" in reviews
    assert "langgraph-checkpoint-postgres" in reviews
    assert "langchain" not in scheduler
    assert "langgraph" not in scheduler
