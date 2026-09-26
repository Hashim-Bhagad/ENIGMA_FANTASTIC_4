"""Stable machine-readable API errors.

Every error response keeps the FastAPI ``detail`` field for backward compatibility and
adds a ``code`` field that clients can branch on without string-matching prose.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Documented codes. Add new codes here so OpenAPI consumers can rely on them.
CODES = {
    "validation_error",
    "unauthorized",
    "forbidden",
    "not_found",
    "conflict",
    "rate_limited",
    "payload_too_large",
    "unsupported_media_type",
    "provider_unavailable",
    "internal_error",
    # Added by the profiles contract: a stale optimistic-concurrency write.
    "profile_version_stale",
}


class ApiError(Exception):
    """Raised to return ``{"detail": ..., "code": ...}`` with an explicit status."""

    def __init__(self, status_code: int, code: str, detail: str):
        if code not in CODES:
            raise ValueError(f"Unknown API error code: {code}")
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


STATUS_CODES = {
    400: "validation_error",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    503: "provider_unavailable",
}


def code_for_status(status_code: int) -> str:
    return STATUS_CODES.get(status_code, "internal_error" if status_code >= 500 else "conflict")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code}
        )

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if not isinstance(detail, str):
            detail = str(detail)
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail, "code": code_for_status(exc.status_code)},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Keep FastAPI's list-shaped detail so existing clients keep working.
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "code": "validation_error"},
        )
