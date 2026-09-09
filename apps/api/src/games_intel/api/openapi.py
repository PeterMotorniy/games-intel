from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from games_intel.api.app import openapi_schema

OPENAPI_RELATIVE = Path("apps/web/openapi.json")


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "config.example.yaml").is_file() and (parent / "pyproject.toml").is_file():
            return parent
    msg = "cannot locate repository root"
    raise RuntimeError(msg)


def render_openapi() -> str:
    return json.dumps(openapi_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_openapi(root: Path | None = None) -> Path:
    base = root or repo_root()
    path = base / OPENAPI_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_openapi(), encoding="utf-8")
    return path


def check_openapi(root: Path | None = None) -> list[str]:
    base = root or repo_root()
    path = base / OPENAPI_RELATIVE
    expected = render_openapi()
    if not path.is_file():
        return [f"missing {OPENAPI_RELATIVE.as_posix()}"]
    if path.read_text(encoding="utf-8") != expected:
        return [f"drift {OPENAPI_RELATIVE.as_posix()}"]
    return []


def schema_dict() -> dict[str, Any]:
    return openapi_schema()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export FastAPI OpenAPI JSON for the web client.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if apps/web/openapi.json drifted",
    )
    args = parser.parse_args(argv)
    if args.check:
        drift = check_openapi()
        if drift:
            print("openapi generation drift:", file=sys.stderr)
            for item in drift:
                print(f"  {item}", file=sys.stderr)
            return 1
        return 0
    write_openapi()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
