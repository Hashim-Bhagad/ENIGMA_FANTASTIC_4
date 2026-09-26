"""Hand-rolled per-process token-bucket rate limiting.

The limiter keeps every bucket in this Python process's memory, protected by a
lock, so it is correct only while the API is served by a single uvicorn worker
(the compose default). With multiple workers or replicas each process enforces
its own budget and the effective limit is multiplied by the process count; a
shared store (for example Redis) would be required for a globally accurate
limit. Buckets are dropped on startup so counters never outlive a process.

``rate_limit(scope, limit, window_seconds, by)`` returns a FastAPI dependency.
The effective limit is read from :class:`~app.config.Settings` on every request
(see ``_SCOPE_SETTINGS``) so operators can retune scopes without a rebuild; the
``limit`` argument is the fallback for scopes without a config field.

Rejections raise :class:`RateLimitExceeded` (an :class:`~app.errors.ApiError`
subclass carrying the ``Retry-After`` header, which ``ApiError`` alone cannot
express) and are answered by ``install_error_handler``.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import ApiError
from app.models import User
from app.security import current_user

logger = logging.getLogger(__name__)

# Scope name -> Settings field holding its per-minute limit.
_SCOPE_SETTINGS = {
    "auth": "rate_limit_auth_per_minute",
    "label_extract": "rate_limit_label_extract_per_minute",
    "provider_reads": "rate_limit_provider_reads_per_minute",
    "recommendations": "rate_limit_recommendations_per_minute",
}


class RateLimitExceeded(ApiError):
    """429 rate_limited carrying a Retry-After header."""

    def __init__(self, detail: str, retry_after: int):
        super().__init__(429, "rate_limited", detail)
        self.headers = {"Retry-After": str(retry_after)}


class _Bucket:
    __slots__ = ("capacity", "refill", "tokens", "updated", "lock")

    def __init__(self, capacity: float, refill_per_second: float):
        self.capacity = float(capacity)
        self.refill = refill_per_second
        self.tokens = float(capacity)
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def consume(self) -> int:
        """Take one token; return 0 on success or a positive Retry-After in seconds."""
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.refill)
            self.updated = now
            if self.tokens >= 1:
                self.tokens -= 1
                return 0
            return max(1, math.ceil((1 - self.tokens) / self.refill))


_buckets: dict[str, _Bucket] = {}
_registry_lock = threading.Lock()


def reset() -> None:
    """Drop every bucket. Called at startup so counters never outlive a process."""
    with _registry_lock:
        _buckets.clear()


def _bucket(key: str, limit: int, window_seconds: int) -> _Bucket:
    with _registry_lock:
        bucket = _buckets.get(key)
        if bucket is None:
            bucket = _Bucket(limit, limit / window_seconds)
            _buckets[key] = bucket
        return bucket


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _enforce(scope: str, limit: int, window_seconds: int, key: str) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    field = _SCOPE_SETTINGS.get(scope)
    effective = getattr(settings, field, limit) if field else limit
    retry_after = _bucket(key, effective, window_seconds).consume()
    if retry_after:
        logger.info("rate limited scope=%s retry_after=%ss", scope, retry_after)
        raise RateLimitExceeded(
            f"Too many requests for {scope}; retry after {retry_after} seconds.", retry_after
        )


def rate_limit(scope: str, limit: int, window_seconds: int, by: Literal["user", "ip"]) -> object:
    """Return a FastAPI dependency that enforces a token bucket for ``scope``."""
    if by == "ip":

        def by_ip(request: Request):
            _enforce(scope, limit, window_seconds, f"{scope}:ip:{_client_ip(request)}")

        return by_ip
    if by == "user":

        def by_user(request: Request, user: User = Depends(current_user)):
            _enforce(scope, limit, window_seconds, f"{scope}:user:{user.id}")

        return by_user
    raise ValueError(f"Unsupported rate-limit key: {by}")


def install_error_handler(app: FastAPI) -> None:
    """Register the 429 handler; must be called after the shared error handlers."""

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
            headers=exc.headers,
        )
