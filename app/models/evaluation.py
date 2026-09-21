"""Persisted JobEvaluationAgent results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobEvaluationRecord(Base):
    __tablename__ = "job_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_fit: Mapped[int] = mapped_column(Integer, nullable=False)
    domain_fit: Mapped[int] = mapped_column(Integer, nullable=False)
    product_fit: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_relevance: Mapped[int] = mapped_column(Integer, nullable=False)
    seniority_fit: Mapped[int] = mapped_column(Integer, nullable=False)
    company_interest_fit: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_strength: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(16), nullable=False)
    strengths: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    concerns: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    missing_information: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    hard_filter: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
