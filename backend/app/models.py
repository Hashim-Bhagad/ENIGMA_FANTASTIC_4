import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


def new_id():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(DOCUMENT)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("source_kind", "source_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    barcode: Mapped[str | None] = mapped_column(String(14), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    source_kind: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(200))
    observation: Mapped[dict] = mapped_column(DOCUMENT)
    raw: Mapped[dict] = mapped_column(DOCUMENT, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"))
    profile_version: Mapped[int] = mapped_column(Integer)
    profile_snapshot: Mapped[dict] = mapped_column(DOCUMENT)
    food_snapshot: Mapped[dict] = mapped_column(DOCUMENT)
    result: Mapped[dict] = mapped_column(DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    result: Mapped[dict] = mapped_column(DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReferenceFood(Base):
    __tablename__ = "reference_foods"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    data: Mapped[dict] = mapped_column(DOCUMENT)
    source: Mapped[dict] = mapped_column(DOCUMENT)


class RecipeRecord(Base):
    __tablename__ = "recipe_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    raw: Mapped[dict] = mapped_column(DOCUMENT)
    source: Mapped[dict] = mapped_column(DOCUMENT)
    review_status: Mapped[str] = mapped_column(String(50), default="pending_schema_validation")


class HealthReport(Base):
    """One uploaded health report: the file's provenance plus the confirmed values.

    The bytes of the uploaded file are never stored or logged; ``source`` keeps only
    the file's name, media type, size, SHA-256 and page count. ``parameters`` holds
    exactly the ``LabParameter`` dumps the deterministic builder produced, so the
    confirmed values need no translation when another service reads this row.
    """

    __tablename__ = "health_reports"
    __table_args__ = (Index("ix_health_reports_owner_created", "owner_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="extracted")
    collected_on: Mapped[str | None] = mapped_column(String(20))
    parameters: Mapped[list] = mapped_column(DOCUMENT, default=list)
    warnings: Mapped[list] = mapped_column(DOCUMENT, default=list)
    source: Mapped[dict] = mapped_column(DOCUMENT, default=dict)
    provider: Mapped[dict] = mapped_column(DOCUMENT, default=dict)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
