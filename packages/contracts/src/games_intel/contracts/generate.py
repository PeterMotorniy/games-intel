from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from games_intel.contracts.adapters import (
    AdapterError,
    AudioResult,
    CanaryParseResult,
    GameDetails,
    GameListing,
    LetsPlaySearch,
    ReviewBatch,
    ReviewSnippet,
    TranscribeResult,
    TranscriptResult,
    VideoHit,
)
from games_intel.contracts.agents import (
    LetsPlayAnalystInput,
    LetsPlayConclusion,
    TranscriptionInput,
    TranscriptionOutput,
)
from games_intel.contracts.envelope import CloudEvent
from games_intel.contracts.payloads import (
    DeadLetter,
    GameCataloged,
    GameLetsPlayAnalyzed,
    GameListed,
    GameReviewsSummarized,
    GameSimilarAssigned,
    GamesPageListed,
    PlatformScore,
    ReviewSummary,
    RunRequested,
    ScheduleTick,
    SimilarGameRef,
    SimilarityRecomputeRequested,
    WorkerHeartbeat,
)
from games_intel.contracts.registry import EVENT_KEY_TO_PAYLOAD
from games_intel.settings import Settings

_CLOUD_EVENT_MODELS: dict[str, type[BaseModel]] = {
    "CloudEventScheduleTick": CloudEvent[ScheduleTick],
    "CloudEventRunRequested": CloudEvent[RunRequested],
    "CloudEventGamesPageListed": CloudEvent[GamesPageListed],
    "CloudEventGameListed": CloudEvent[GameListed],
    "CloudEventGameCataloged": CloudEvent[GameCataloged],
    "CloudEventGameReviewsSummarized": CloudEvent[GameReviewsSummarized],
    "CloudEventGameLetsPlayAnalyzed": CloudEvent[GameLetsPlayAnalyzed],
    "CloudEventGameSimilarAssigned": CloudEvent[GameSimilarAssigned],
    "CloudEventSimilarityRecomputeRequested": CloudEvent[SimilarityRecomputeRequested],
    "CloudEventWorkerHeartbeat": CloudEvent[WorkerHeartbeat],
    "CloudEventDeadLetter": CloudEvent[DeadLetter],
}


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "config.example.yaml").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    msg = "cannot locate repository root"
    raise RuntimeError(msg)


def _dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _dump_yaml(payload: Mapping[str, Any]) -> str:
    dumped = yaml.safe_dump(payload, sort_keys=True, allow_unicode=True)
    return dumped if dumped.endswith("\n") else dumped + "\n"


def _schema_models() -> dict[str, type[BaseModel]]:
    models: dict[str, type[BaseModel]] = {
        "CloudEvent": CloudEvent[dict[str, Any]],
        "PlatformScore": PlatformScore,
        "ReviewSummary": ReviewSummary,
        "SimilarGameRef": SimilarGameRef,
        "ReviewSnippet": ReviewSnippet,
        "LetsPlayConclusion": LetsPlayConclusion,
        "LetsPlayAnalystInput": LetsPlayAnalystInput,
        "TranscriptionInput": TranscriptionInput,
        "TranscriptionOutput": TranscriptionOutput,
        "AdapterError": AdapterError,
        "GameListing": GameListing,
        "GameDetails": GameDetails,
        "ReviewBatch": ReviewBatch,
        "CanaryParseResult": CanaryParseResult,
        "VideoHit": VideoHit,
        "LetsPlaySearch": LetsPlaySearch,
        "TranscriptResult": TranscriptResult,
        "AudioResult": AudioResult,
        "TranscribeResult": TranscribeResult,
    }
    for payload_cls in EVENT_KEY_TO_PAYLOAD.values():
        models[payload_cls.__name__] = payload_cls
    models.update(_CLOUD_EVENT_MODELS)
    return models


def build_asyncapi() -> dict[str, Any]:
    settings = Settings()
    channels: dict[str, Any] = {}
    operations: dict[str, Any] = {}
    messages: dict[str, Any] = {}
    for event_key, payload_cls in EVENT_KEY_TO_PAYLOAD.items():
        address = settings.event_name(event_key)
        message_name = payload_cls.__name__
        schema_file = f"./schemas/CloudEvent{payload_cls.__name__}.json"
        messages[message_name] = {
            "name": message_name,
            "contentType": "application/json",
            "payload": {"$ref": schema_file},
        }
        channel_id = address.replace(".", "_")
        channels[channel_id] = {
            "address": address,
            "messages": {message_name: {"$ref": f"#/components/messages/{message_name}"}},
        }
        operations[f"send_{channel_id}"] = {
            "action": "send",
            "channel": {"$ref": f"#/channels/{channel_id}"},
        }
        operations[f"receive_{channel_id}"] = {
            "action": "receive",
            "channel": {"$ref": f"#/channels/{channel_id}"},
        }
    return {
        "asyncapi": "3.0.0",
        "info": {
            "title": "Games Intel Events",
            "version": "0.1.0",
            "description": "Generated from Pydantic CloudEvents contracts. Do not edit by hand.",
        },
        "servers": {
            "kafka": {
                "host": settings.kafka.bootstrap_servers,
                "protocol": "kafka",
            }
        },
        "channels": channels,
        "operations": operations,
        "components": {"messages": messages},
    }


def render_artifacts() -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for name, model in _schema_models().items():
        artifacts[f"contracts/schemas/{name}.json"] = _dump_json(model.model_json_schema())
    artifacts["contracts/asyncapi.yaml"] = _dump_yaml(build_asyncapi())
    return artifacts


def write_artifacts(root: Path | None = None) -> dict[str, str]:
    base = root or repo_root()
    artifacts = render_artifacts()
    for relative, content in artifacts.items():
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return artifacts


def check_artifacts(root: Path | None = None) -> list[str]:
    base = root or repo_root()
    expected = render_artifacts()
    drift: list[str] = []
    for relative, content in expected.items():
        path = base / relative
        if not path.is_file():
            drift.append(f"missing {relative}")
            continue
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            drift.append(f"drift {relative}")
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate JSON Schema and AsyncAPI from Pydantic.")
    parser.add_argument("--check", action="store_true", help="fail if generated files drifted")
    args = parser.parse_args(argv)
    if args.check:
        drift = check_artifacts()
        if drift:
            print("schema generation drift:", file=sys.stderr)
            for item in drift:
                print(f"  {item}", file=sys.stderr)
            return 1
        return 0
    write_artifacts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
