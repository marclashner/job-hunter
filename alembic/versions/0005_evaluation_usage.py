"""Usage and cost metadata on job evaluations.

Revision ID: 0005_evaluation_usage
Revises: 0004_job_evaluations
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_evaluation_usage"
down_revision: str | None = "0004_job_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_evaluations", sa.Column("usage_input_tokens", sa.Integer(), nullable=True))
    op.add_column("job_evaluations", sa.Column("usage_output_tokens", sa.Integer(), nullable=True))
    op.add_column("job_evaluations", sa.Column("usage_total_tokens", sa.Integer(), nullable=True))
    op.add_column("job_evaluations", sa.Column("usage_requests", sa.Integer(), nullable=True))
    op.add_column(
        "job_evaluations",
        sa.Column("estimated_cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
    )
    op.add_column(
        "job_evaluations",
        sa.Column(
            "usage_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("job_evaluations", "usage_metadata")
    op.drop_column("job_evaluations", "estimated_cost_usd")
    op.drop_column("job_evaluations", "usage_requests")
    op.drop_column("job_evaluations", "usage_total_tokens")
    op.drop_column("job_evaluations", "usage_output_tokens")
    op.drop_column("job_evaluations", "usage_input_tokens")
