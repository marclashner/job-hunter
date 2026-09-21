"""Job evaluations table.

Revision ID: 0004_job_evaluations
Revises: 0003_jobs
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_job_evaluations"
down_revision: str | None = "0003_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("technical_fit", sa.Integer(), nullable=False),
        sa.Column("domain_fit", sa.Integer(), nullable=False),
        sa.Column("product_fit", sa.Integer(), nullable=False),
        sa.Column("ai_relevance", sa.Integer(), nullable=False),
        sa.Column("seniority_fit", sa.Integer(), nullable=False),
        sa.Column("company_interest_fit", sa.Integer(), nullable=False),
        sa.Column("evidence_strength", sa.Integer(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("concerns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_information", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "supporting_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("hard_filter", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_job_evaluations_job_id", "job_evaluations", ["job_id"])
    op.create_index("ix_job_evaluations_profile_id", "job_evaluations", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_job_evaluations_profile_id", table_name="job_evaluations")
    op.drop_index("ix_job_evaluations_job_id", table_name="job_evaluations")
    op.drop_table("job_evaluations")
