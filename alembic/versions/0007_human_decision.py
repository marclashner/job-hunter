"""Human review fields on jobs.

Revision ID: 0007_human_decision
Revises: 0006_evaluation_provenance
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_human_decision"
down_revision: str | None = "0006_evaluation_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("human_decision", sa.String(length=16), nullable=True))
    op.add_column("jobs", sa.Column("human_decided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_jobs_human_decision", "jobs", ["human_decision"])


def downgrade() -> None:
    op.drop_index("ix_jobs_human_decision", table_name="jobs")
    op.drop_column("jobs", "human_decided_at")
    op.drop_column("jobs", "human_decision")
