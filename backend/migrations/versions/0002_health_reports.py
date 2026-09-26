"""Uploaded health reports, their deterministic parameters and warnings."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_health_reports"
down_revision = "0001_initial"
branch_labels = None
depends_on = None
DOC = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade():
    op.create_table(
        "health_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("collected_on", sa.String(20)),
        sa.Column("parameters", DOC, nullable=False),
        sa.Column("warnings", DOC, nullable=False),
        sa.Column("source", DOC, nullable=False),
        sa.Column("provider", DOC, nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_health_reports_owner_id", "health_reports", ["owner_id"])
    op.create_index(
        "ix_health_reports_owner_created", "health_reports", ["owner_id", "created_at"]
    )


def downgrade():
    op.drop_index("ix_health_reports_owner_created", table_name="health_reports")
    op.drop_index("ix_health_reports_owner_id", table_name="health_reports")
    op.drop_table("health_reports")
