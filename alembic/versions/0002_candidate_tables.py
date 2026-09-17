"""Candidate profile and evidence tables.

Revision ID: 0002_candidate
Revises: 0001_initial
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_candidate"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("target_titles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("seniority", sa.String(length=32), nullable=True),
        sa.Column("years_experience", sa.Float(), nullable=True),
        sa.Column("preferred_locations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("remote_preference", sa.String(length=32), nullable=True),
        sa.Column("minimum_compensation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("target_compensation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "employment_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("industries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "preferred_company_stages", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("domains", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ai_experience", sa.Text(), nullable=True),
        sa.Column("healthcare_experience", sa.Text(), nullable=True),
        sa.Column("leadership_experience", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("field_grounding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("key", name="uq_candidate_profiles_key"),
    )
    op.create_table(
        "candidate_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("detailed_description", sa.Text(), nullable=False),
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("measurable_outcomes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("profile_id", "key", name="uq_candidate_evidence_profile_key"),
    )
    op.create_index("ix_candidate_evidence_profile_id", "candidate_evidence", ["profile_id"])
    op.create_index("ix_candidate_evidence_category", "candidate_evidence", ["category"])


def downgrade() -> None:
    op.drop_index("ix_candidate_evidence_category", table_name="candidate_evidence")
    op.drop_index("ix_candidate_evidence_profile_id", table_name="candidate_evidence")
    op.drop_table("candidate_evidence")
    op.drop_table("candidate_profiles")
