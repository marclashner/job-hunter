"""Review dashboard and human-decision schemas. Not application submission."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import HumanDecision, JobSource, Recommendation, RemotePolicy, SalarySource
from app.schemas.candidate import CandidateEvidenceRead
from app.schemas.evaluation import JobEvaluationRead
from app.schemas.job import JobRead
from app.scoring.hard_filters import HardFilterResult


class ReviewSummary(BaseModel):
    discovered_today: int
    evaluated: int
    recommended_applications: int
    needing_review: int
    applications_submitted: int = 0
    interviews: int = 0
    offers: int = 0


class JobQueueItem(BaseModel):
    id: UUID
    company: str
    title: str
    location: str | None
    compensation: str
    salary_source: SalarySource | None = None
    salary_quote: str | None = None
    eligible_countries: list[str]
    score: int | None
    recommendation: Recommendation | None
    top_strengths: list[str]
    concerns: list[str]
    source: JobSource
    remote_policy: RemotePolicy | None
    discovered_at: datetime
    human_decision: HumanDecision | None
    application_url: str | None


class JobQueueResponse(BaseModel):
    items: list[JobQueueItem]
    total: int
    limit: int
    offset: int


class JobReviewDetail(BaseModel):
    job: JobRead
    evaluation: JobEvaluationRead | None
    supporting_evidence: list[CandidateEvidenceRead]
    hard_filter: HardFilterResult | None
    application_url: str | None
    human_decision: HumanDecision | None


class HumanDecisionRequest(BaseModel):
    decision: HumanDecision
