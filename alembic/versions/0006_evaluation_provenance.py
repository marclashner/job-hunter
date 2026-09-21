"""Evaluation provenance: live vs offline vs mock.

Revision ID: 0006_evaluation_provenance
Revises: 0005_evaluation_usage
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_evaluation_provenance"
down_revision: str | None = "0005_evaluation_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_evaluations",
        sa.Column(
            "evaluation_mode",
            sa.String(length=32),
            nullable=False,
            server_default="live_llm",
        ),
    )
    op.alter_column(
        "job_evaluations",
        "model",
        existing_type=sa.String(length=128),
        nullable=True,
    )
    op.add_column("job_evaluations", sa.Column("provider", sa.String(length=64), nullable=True))
    op.add_column(
        "job_evaluations",
        sa.Column("llm_request_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "job_evaluations",
        sa.Column("fallback_reason", sa.String(length=255), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE job_evaluations
            SET evaluation_mode = 'offline_rubric',
                model = NULL,
                provider = NULL,
                llm_request_id = NULL,
                fallback_reason = NULL
            WHERE model = 'hard-filter'
            """
        )
    )
    op.create_index("ix_job_evaluations_evaluation_mode", "job_evaluations", ["evaluation_mode"])


def downgrade() -> None:
    op.drop_index("ix_job_evaluations_evaluation_mode", table_name="job_evaluations")
    op.execute(
        sa.text(
            """
            UPDATE job_evaluations
            SET model = COALESCE(model, 'unknown')
            WHERE model IS NULL
            """
        )
    )
    op.drop_column("job_evaluations", "fallback_reason")
    op.drop_column("job_evaluations", "llm_request_id")
    op.drop_column("job_evaluations", "provider")
    op.alter_column(
        "job_evaluations",
        "model",
        existing_type=sa.String(length=128),
        nullable=False,
    )
    op.drop_column("job_evaluations", "evaluation_mode")
