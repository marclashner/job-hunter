"""ORM mappings for candidate profile and evidence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CandidateProfile(Base):
    """Structured candidate record used by agents to evaluate jobs and write applications."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (UniqueConstraint("key", name="uq_candidate_profiles_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_titles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    years_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_locations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    remote_preference: Mapped[str | None] = mapped_column(String(32), nullable=True)
    minimum_compensation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    target_compensation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    employment_preferences: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    industries: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    preferred_company_stages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    technologies: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    ai_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    healthcare_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    leadership_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_grounding: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    evidence: Mapped[list[CandidateEvidence]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="CandidateEvidence.created_at",
    )


class CandidateEvidence(Base):
    """Atomic, source-backed claim. Agents may not invent claims beyond these rows."""

    __tablename__ = "candidate_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_description: Mapped[str] = mapped_column(Text, nullable=False)
    technologies: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    measurable_outcomes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile: Mapped[CandidateProfile] = relationship(back_populates="evidence")

    __table_args__ = (
        UniqueConstraint("profile_id", "key", name="uq_candidate_evidence_profile_key"),
    )
