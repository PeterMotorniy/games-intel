from __future__ import annotations

import json
import logging
import re
from typing import Any

_HTML_RE = re.compile(r"</?[a-zA-Z!?][^>]*>", re.IGNORECASE)
_SECRET_IN_TEXT_RE = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*\S+"
)
_QUERY_SECRET_RE = re.compile(r"([?&](?:key|api_key|token)=)[^&\s\"']+", re.IGNORECASE)
_SECRET_KEYS = frozenset(
    {
        "token",
        "api_key",
        "apikey",
        "password",
        "secret",
        "authorization",
        "html",
        "body",
        "transcript",
    }
)


def redact_url_secrets(message: str) -> str:
    return _QUERY_SECRET_RE.sub(r"\1[redacted]", message)


class UrlSecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_url_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: redact_url_secrets(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            else:
                record.args = tuple(
                    redact_url_secrets(arg) if isinstance(arg, str) else arg for arg in record.args
                )
        return True


def configure_process_logging() -> None:
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    httpx_logger.addFilter(UrlSecretFilter())
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def sanitize_error_message(message: str, *, limit: int = 500) -> str:
    if _HTML_RE.search(message):
        return "html omitted"
    cleaned = _SECRET_IN_TEXT_RE.sub("[redacted]", message.replace("\x00", ""))
    cleaned = redact_url_secrets(cleaned)
    if len(cleaned) > limit:
        return cleaned[:limit] + "…"
    return cleaned


def emit_json(
    logger: logging.Logger,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if key.lower() in _SECRET_KEYS:
            continue
        if isinstance(value, str) and _HTML_RE.search(value):
            payload[key] = "html omitted"
            continue
        if isinstance(value, str):
            payload[key] = redact_url_secrets(_SECRET_IN_TEXT_RE.sub("[redacted]", value))
            continue
        payload[key] = value
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
