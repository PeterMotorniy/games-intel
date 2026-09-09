from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from games_intel.api.schemas import ProblemDetails

PROBLEM_JSON = "application/problem+json"


class ProblemError(Exception):
    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        *,
        type: str = "about:blank",
        extras: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.title = title
        self.detail = detail
        self.type = type
        self.extras = extras or {}
        super().__init__(detail or title)


class DatabaseUnavailableError(ProblemError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "Service Unavailable",
            "PostgreSQL is unavailable",
            extras={"postgres": False},
        )


def problem_response(error: ProblemError) -> JSONResponse:
    payload = ProblemDetails(
        type=error.type,
        title=error.title,
        status=error.status,
        detail=error.detail,
    ).model_dump(exclude_none=True)
    payload.update(error.extras)
    return JSONResponse(
        status_code=error.status,
        content=payload,
        media_type=PROBLEM_JSON,
    )


async def problem_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ProblemError):
        raise exc
    return problem_response(exc)


async def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    detail = exc.detail if isinstance(exc.detail, str) else None
    title = "Not Found" if exc.status_code == 404 else "HTTP Error"
    return problem_response(ProblemError(exc.status_code, title, detail))


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    first = exc.errors()[0] if exc.errors() else None
    loc = ".".join(str(part) for part in first["loc"]) if first else "request"
    message = str(first["msg"]) if first else "invalid request"
    return problem_response(
        ProblemError(400, "Bad Request", f"{loc}: {message}"),
    )
