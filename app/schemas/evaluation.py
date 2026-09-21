"""Structured job-evaluation output. Experience claims must cite CandidateEvidence IDs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import EvaluationMode, JobSource, Recommendation
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
    evaluation_mode: EvaluationMode
    model: str | None = None
    provider: str | None = None
    llm_request_id: str | None = None
    fallback_reason: str | None = None
    hard_filter: HardFilterResult
    created_at: datetime
    updated_at: datetime


class EvaluateJobRequest(BaseModel):
    evaluation_mode: EvaluationMode = EvaluationMode.LIVE_LLM


class BatchEvaluationRequest(BaseModel):
    source: JobSource | None = None
    discovered_after: datetime | None = None
    discovered_before: datetime | None = None
    limit: int | None = Field(default=None, ge=1, le=500)
    dry_run: bool = False
    reevaluate: bool = False
    concurrency: int | None = Field(default=None, ge=1, le=16)
    evaluation_mode: EvaluationMode = EvaluationMode.LIVE_LLM

    @model_validator(mode="after")
    def date_range_is_ordered(self) -> BatchEvaluationRequest:
        if (
            self.discovered_after is not None
            and self.discovered_before is not None
            and self.discovered_after > self.discovered_before
        ):
            raise ValueError("discovered_after must be less than or equal to discovered_before")
        return self


class BatchEvaluationError(BaseModel):
    job_id: UUID | None = None
    stage: str
    detail: str


class ModelUsageSummary(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    estimated_cost_usd: float | None = None


class BatchEvaluationResult(BaseModel):
    discovered: int
    hard_filtered: int
    evaluated: int
    apply: int
    review: int
    reject: int
    errors: list[BatchEvaluationError]
    dry_run: bool = False
    usage: ModelUsageSummary = Field(default_factory=ModelUsageSummary)
