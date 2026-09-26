from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api import accounts, assessments, labels, products
from app.config import Settings, get_settings
from app.db import get_session
from app.integrations.models import ModelAssist
from app.integrations.off import OpenFoodFacts


def create_app(settings: Settings | None = None):
    settings = settings or get_settings()
    migration_heads = set(
        ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations")).get_heads()
    )

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            timeout=settings.provider_timeout, follow_redirects=False
        ) as client:
            app.state.off = OpenFoodFacts(client, settings.off_user_agent)
            app.state.models = ModelAssist(client, settings)
            yield

    app = FastAPI(
        title="Dietary Risk API",
        version="0.1.0",
        lifespan=lifespan,
        description="Supported personal dietary checks with explicit evidence and missing-information states.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for router in (accounts.router, products.router, assessments.router, labels.router):
        app.include_router(router)

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    def ready(session: Session = Depends(get_session)):
        try:
            installed = set(session.scalars(text("SELECT version_num FROM alembic_version")))
        except SQLAlchemyError as exc:
            session.rollback()
            raise HTTPException(503, "Database or migrations are unavailable") from exc
        if installed != migration_heads:
            raise HTTPException(503, "Database migrations are not current")
        return {"status": "ready", "database": "connected", "migrations": "current"}

    return app


app = create_app()
