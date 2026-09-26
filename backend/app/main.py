import importlib.util
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import accounts, assessments, labels, products, recipes, verification
from app.config import Settings, get_settings
from app.db import get_session
from app.errors import register_error_handlers
from app.integrations.models import ModelAssist
from app.integrations.off import OpenFoodFacts
from app.integrations.theverifico import FssaiVerifier
from app.rate_limit import install_error_handler
from app.rate_limit import reset as reset_rate_limits

logger = logging.getLogger(__name__)

# Bytes consumed from a rejected request before answering, so clients can read the 413
# instead of seeing a connection reset while they are still uploading.
DRAIN_BYTES = 8 * 1024 * 1024


class BodySizeLimitMiddleware:
    """Reject oversized request bodies before a route can buffer them.

    The declared ``Content-Length`` is checked first, then bytes are counted as
    they arrive so a chunked upload without a length is still bounded. The
    multipart label upload keeps its own 5 MiB read cap inside the route; this
    global cap only bounds the whole request body.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def _drain(self, receive, limit: int) -> None:
        """Consume a bounded amount of a rejected body so the client can read the 413.

        Without this, a client still writing a large upload sees a reset connection
        instead of the status code.
        """
        drained = 0
        while drained < limit:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            drained += len(message.get("body", b""))
            if not message.get("more_body", False):
                return

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break
                if declared > self.max_bytes:
                    logger.info("rejected oversized request body declared_bytes=%s", declared)
                    await self._drain(receive, min(declared, self.max_bytes + DRAIN_BYTES))
                    await self._reject(send)
                    return
                break
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                logger.info("rejected oversized request body bytes=%s", total)
                await self._drain(receive, DRAIN_BYTES)
                await self._reject(send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        payload = b"".join(chunks)
        replayed = False

        async def replay_receive():
            nonlocal replayed
            if replayed:
                return {"type": "http.request", "body": b"", "more_body": False}
            replayed = True
            return {"type": "http.request", "body": payload, "more_body": False}

        await self.app(scope, replay_receive, send)

    async def _reject(self, send):
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body is too large", "code": "payload_too_large"},
        )
        await response({"type": "http", "headers": []}, _empty_receive, send)


async def _empty_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


def create_app(settings: Settings | None = None):
    settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    migration_heads = set(
        ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations")).get_heads()
    )

    @asynccontextmanager
    async def lifespan(app):
        reset_rate_limits()
        async with httpx.AsyncClient(
            timeout=settings.provider_timeout, follow_redirects=False
        ) as client:
            app.state.off = OpenFoodFacts(client, settings.off_user_agent)
            app.state.models = ModelAssist(client, settings)
            verifico_key = (
                settings.theverifico_api_key.get_secret_value()
                if settings.theverifico_api_key
                else None
            )
            app.state.fssai = FssaiVerifier(client, verifico_key)
            yield

    app = FastAPI(
        title="Dietary Risk API",
        version="0.1.0",
        lifespan=lifespan,
        description="Supported personal dietary checks with explicit evidence and missing-information states.",
    )
    # Body cap is added first so CORS ends up outermost and can decorate the 413.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    install_error_handler(app)

    routers = [
        accounts.router,
        assessments.router,
        labels.router,
        products.router,
        recipes.router,
        verification.router,
    ]
    for module_name in ("dishes", "reports", "intake", "conditions"):
        if importlib.util.find_spec(f"app.api.{module_name}") is not None:
            module = importlib.import_module(f"app.api.{module_name}")
            routers.append(module.router)
    for router in routers:
        app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled error on %s %s (%s)",
            request.method,
            request.url.path,
            type(exc).__name__,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error", "code": "internal_error"}
        )

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    def ready(session: Session = Depends(get_session)):
        try:
            installed = set(session.scalars(text("SELECT version_num FROM alembic_version")))
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error("readiness check failed: %s", type(exc).__name__)
            raise HTTPException(503, "Database or migrations are unavailable") from exc
        if installed != migration_heads:
            raise HTTPException(503, "Database migrations are not current")
        return {"status": "ready", "database": "connected", "migrations": "current"}

    return app


app = create_app()
