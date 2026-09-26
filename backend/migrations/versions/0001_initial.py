"""Initial account, observation, assessment, and reference schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
DOC = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", DOC, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_profiles_owner_id", "profiles", ["owner_id"], unique=True)
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("barcode", sa.String(14)),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("observation", DOC, nullable=False),
        sa.Column("raw", DOC, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_kind", "source_id"),
    )
    op.create_index("ix_products_barcode", "products", ["barcode"], unique=True)
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id"), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("profile_snapshot", DOC, nullable=False),
        sa.Column("food_snapshot", DOC, nullable=False),
        sa.Column("result", DOC, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assessments_owner_id", "assessments", ["owner_id"])
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("assessments.id"), nullable=False),
        sa.Column("result", DOC, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendation_runs_owner_id", "recommendation_runs", ["owner_id"])
    op.create_index(
        "ix_recommendation_runs_assessment_id", "recommendation_runs", ["assessment_id"]
    )
    op.create_table(
        "reference_foods",
        sa.Column("code", sa.String(20), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("data", DOC, nullable=False),
        sa.Column("source", DOC, nullable=False),
    )
    op.create_index("ix_reference_foods_name", "reference_foods", ["name"])
    op.create_table(
        "recipe_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("raw", DOC, nullable=False),
        sa.Column("source", DOC, nullable=False),
        sa.Column("review_status", sa.String(50), nullable=False),
    )


def downgrade():
    for table in [
        "recipe_records",
        "reference_foods",
        "recommendation_runs",
        "assessments",
        "products",
        "profiles",
        "users",
    ]:
        op.drop_table(table)
