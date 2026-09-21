"""Structured job-evaluation output. Experience claims must cite CandidateEvidence IDs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Recommendation
from app.scoring.hard_filters import HardFilterResult


class JobEvaluation(BaseModel):
    """Whether a listing is worth the candidate's time. Not an application."""

    overall_score: int = Field(ge=0, le=100)
    technical_fit: int = Field(ge=0, le=25)
    domain_fit: int = Field(ge=0, le=20)
    product_fit: int = Field(ge=0, le=15)
    ai_relevance: int = Field(ge=0, le=15)
    seniority_fit: int = Field(ge=0, le=10)
    company_interest_fit: int = Field(ge=0, le=10)
    evidence_strength: int = Field(ge=0, le=5)
    recommendation: Recommendation
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def overall_score_matches_components(self) -> JobEvaluation:
        total = (
            self.technical_fit
            + self.domain_fit
            + self.product_fit
            + self.ai_relevance
            + self.seniority_fit
            + self.company_interest_fit
            + self.evidence_strength
        )
        if total > 100:
            raise ValueError("component scores cannot exceed 100")
        self.overall_score = total
        return self


class JobEvaluationRead(JobEvaluation):
    id: UUID
    job_id: UUID
    profile_id: UUID
    model: str
    hard_filter: HardFilterResult
    created_at: datetime
    updated_at: datetime
