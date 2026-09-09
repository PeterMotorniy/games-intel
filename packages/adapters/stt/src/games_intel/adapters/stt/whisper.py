from __future__ import annotations

from typing import Any

import httpx

from games_intel.adapters.stt.exceptions import SttAdapterError
from games_intel.adapters.stt.files import resolve_audio_path
from games_intel.contracts.adapters import AdapterErrorCode, TranscribeInput, TranscribeResult
from games_intel.settings import Settings

_STATUS_TO_CODE: dict[int, AdapterErrorCode] = {
    401: "unavailable",
    403: "unavailable",
    404: "unavailable",
    408: "timeout",
    413: "unavailable",
    429: "rate_limited",
    422: "parse_error",
    503: "unavailable",
    504: "timeout",
}

_AUDIO_MIME: dict[str, str] = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


class OpenAiWhisperStt:
    """OpenAI Whisper API (`POST /v1/audio/translations`) — English transcript."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        stt = settings.stt
        timeout = httpx.Timeout(stt.timeout_seconds)
        base_url = stt.base_url.strip().rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._model = stt.model
        self._api_key = stt.api_key.get_secret_value().strip()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def transcribe(self, inp: TranscribeInput) -> TranscribeResult:
        if not self._api_key:
            raise SttAdapterError("unavailable", "openai api_key is not configured")
        path = resolve_audio_path(inp.audio_ref)
        audio = path.read_bytes()
        mime = _AUDIO_MIME.get(path.suffix.lower(), "application/octet-stream")
        files = {"file": (path.name or "audio.bin", audio, mime)}
        data = {"model": self._model, "response_format": "verbose_json"}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = await self._client.post(
                "/audio/translations",
                files=files,
                data=data,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise SttAdapterError("timeout", "stt request timed out") from exc
        except httpx.HTTPError as exc:
            raise SttAdapterError("unavailable", "stt API unavailable") from exc
        if response.status_code != 200:
            code: AdapterErrorCode = _STATUS_TO_CODE.get(response.status_code, "unavailable")
            if response.status_code >= 500:
                code = "unavailable"
            raise SttAdapterError(code, f"stt HTTP {response.status_code}")
        try:
            body: Any = response.json()
        except ValueError as exc:
            raise SttAdapterError("parse_error", "stt response is not JSON") from exc
        return _parse_transcript(body)


def _parse_transcript(body: object) -> TranscribeResult:
    if not isinstance(body, dict):
        raise SttAdapterError("parse_error", "stt body must be an object")
    text = body.get("text")
    if not isinstance(text, str):
        raise SttAdapterError("parse_error", "stt text missing")
    return TranscribeResult(
        text=text.strip(),
        language="en",
    )
