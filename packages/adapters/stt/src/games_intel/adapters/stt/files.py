from __future__ import annotations

import tempfile
from pathlib import Path

from games_intel.adapters.stt.exceptions import SttAdapterError


def resolve_audio_path(audio_ref: str) -> Path:
    path = Path(audio_ref).expanduser().resolve()
    if not path.is_file():
        raise SttAdapterError("not_found", "stt audio_ref is not a file")
    tmp = Path(tempfile.gettempdir()).resolve()
    if path != tmp and tmp not in path.parents:
        raise SttAdapterError("not_found", "stt audio_ref is outside temp dir")
    return path


def read_audio_bytes(audio_ref: str) -> bytes:
    return resolve_audio_path(audio_ref).read_bytes()
