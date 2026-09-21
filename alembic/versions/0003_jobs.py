"""Job listings table.

Revision ID: 0003_jobs
Revises: 0002_candidate
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_jobs"
down_revision: str | None = "0002_candidate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_job_id", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("remote_policy", sa.String(length=32), nullable=True),
        sa.Column("employment_type", sa.String(length=32), nullable=True),
        sa.Column("seniority", sa.String(length=32), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("job_url", sa.String(length=2048), nullable=True),
        sa.Column("application_url", sa.String(length=2048), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source", "source_job_id", name="uq_jobs_source_source_job_id"),
    )
    op.create_index("ix_jobs_source", "jobs", ["source"])
    op.create_index("ix_jobs_title", "jobs", ["title"])
    op.create_index("ix_jobs_location", "jobs", ["location"])
    op.create_index("ix_jobs_remote_policy", "jobs", ["remote_policy"])
    op.create_index("ix_jobs_seniority", "jobs", ["seniority"])
    op.create_index("ix_jobs_salary_min", "jobs", ["salary_min"])
    op.create_index("ix_jobs_content_hash", "jobs", ["content_hash"])
    op.create_index("ix_jobs_discovered_at", "jobs", ["discovered_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_discovered_at", table_name="jobs")
    op.drop_index("ix_jobs_content_hash", table_name="jobs")
    op.drop_index("ix_jobs_salary_min", table_name="jobs")
    op.drop_index("ix_jobs_seniority", table_name="jobs")
    op.drop_index("ix_jobs_remote_policy", table_name="jobs")
    op.drop_index("ix_jobs_location", table_name="jobs")
    op.drop_index("ix_jobs_title", table_name="jobs")
    op.drop_index("ix_jobs_source", table_name="jobs")
    op.drop_table("jobs")
