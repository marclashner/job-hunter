"""Salary provenance and eligible countries on jobs.

Revision ID: 0008_job_salary_geo
Revises: 0007_human_decision
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_job_salary_geo"
down_revision: str | None = "0007_human_decision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("salary_source", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("salary_quote", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "eligible_countries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "eligible_countries")
    op.drop_column("jobs", "salary_quote")
    op.drop_column("jobs", "salary_source")
