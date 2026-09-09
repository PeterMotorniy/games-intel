from __future__ import annotations

from typing import Any

from games_intel.adapters.youtube.exceptions import YoutubeAdapterError
from games_intel.contracts.adapters import AdapterErrorCode

_STATUS_TO_CODE: dict[int, AdapterErrorCode] = {
    404: "not_found",
    408: "timeout",
    429: "rate_limited",
    503: "unavailable",
    504: "timeout",
}

_QUOTA_REASONS = frozenset({"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"})


def map_youtube_http_error(status_code: int, body: object) -> YoutubeAdapterError:
    if status_code == 403 and _body_is_quota(body):
        return YoutubeAdapterError("quota_exceeded", "youtube quota exceeded")
    if status_code == 429:
        return YoutubeAdapterError("quota_exceeded", "youtube rate limited")
    code: AdapterErrorCode = _STATUS_TO_CODE.get(status_code, "unavailable")
    if status_code >= 500:
        code = "unavailable"
    return YoutubeAdapterError(code, f"youtube HTTP {status_code}")


def _body_is_quota(body: object) -> bool:
    if not isinstance(body, dict):
        return False
    error = body.get("error")
    if not isinstance(error, dict):
        return False
    status = str(error.get("status", ""))
    if status in {"RESOURCE_EXHAUSTED", "PERMISSION_DENIED"} and _message_is_quota(error):
        return True
    if error.get("reason") in _QUOTA_REASONS:
        return True
    errors = error.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict) and item.get("reason") in _QUOTA_REASONS:
                return True
            if isinstance(item, dict) and str(item.get("domain", "")).endswith("quota"):
                return True
    return _message_is_quota(error)


def _message_is_quota(error: dict[str, Any]) -> bool:
    message = str(error.get("message", "")).casefold()
    return "quota" in message and "exceed" in message
