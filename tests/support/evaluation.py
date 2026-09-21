"""Shared JobEvaluationAgent test doubles and a synthetic candidate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.agents.job_evaluation import JobEvaluationContext
from app.models.enums import (
    ConfidenceLevel,
    EmploymentType,
    EvidenceCategory,
    EvidenceSource,
    JobSource,
    Provenance,
    Recommendation,
    RemotePolicy,
    RemotePreference,
    Seniority,
)
from app.schemas.candidate import CandidateEvidenceRead, CandidateProfileRead, Compensation
from app.schemas.evaluation import JobEvaluation
from app.schemas.grounding import GroundedValue
from app.schemas.job import JobRead

EVIDENCE_BACKEND = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
EVIDENCE_HEALTHCARE = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_AI = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PROFILE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def _backed[T](value: T) -> GroundedValue[T]:
    return GroundedValue(
        value=value,
        provenance=Provenance.EVIDENCE_BACKED,
        evidence_ids=[EVIDENCE_BACKEND],
    )


def _derived[T](value: T) -> GroundedValue[T]:
    return GroundedValue(
        value=value,
        provenance=Provenance.DERIVED,
        evidence_ids=[EVIDENCE_BACKEND],
        interpretation_notes="Synthetic test derivation.",
    )


def synthetic_evidence() -> list[CandidateEvidenceRead]:
    return [
        CandidateEvidenceRead(
            id=EVIDENCE_BACKEND,
            key="backend",
            category=EvidenceCategory.BACKEND,
            claim="Built production Python APIs and PostgreSQL services.",
            detailed_description="Owned FastAPI services, PostgreSQL, and on-call.",
            technologies=["Python", "PostgreSQL", "FastAPI"],
            measurable_outcomes=["Reduced p95 latency"],
            source=EvidenceSource.RESUME,
            confidence=ConfidenceLevel.HIGH,
            tags=["backend"],
        ),
        CandidateEvidenceRead(
            id=EVIDENCE_HEALTHCARE,
            key="healthcare",
            category=EvidenceCategory.HEALTHCARE,
            claim="Shipped healthcare operations software.",
            detailed_description="HIPAA-aware workflow systems for clinical operations.",
            technologies=["Python"],
            measurable_outcomes=["Automated routing"],
            source=EvidenceSource.RESUME,
            confidence=ConfidenceLevel.HIGH,
            tags=["healthcare"],
        ),
        CandidateEvidenceRead(
            id=EVIDENCE_AI,
            key="ai",
            category=EvidenceCategory.AI,
            claim="Building LLM workflow automation in a current project.",
            detailed_description="Structured LLM workflows; not a claim of years of production ML.",
            technologies=["Python", "LLMs"],
            measurable_outcomes=[],
            source=EvidenceSource.CURRENT_PROJECT,
            confidence=ConfidenceLevel.MEDIUM,
            tags=["ai"],
        ),
    ]


def synthetic_profile(evidence: list[CandidateEvidenceRead] | None = None) -> CandidateProfileRead:
    rows = evidence if evidence is not None else synthetic_evidence()
    demonstrated = [
        EvidenceCategory.BACKEND,
        EvidenceCategory.HEALTHCARE,
        EvidenceCategory.AI,
    ]
    return CandidateProfileRead(
        id=PROFILE_ID,
        key="primary",
        name=_backed("Test Candidate"),
        target_titles=_derived(
            ["Senior Software Engineer", "Senior Backend Engineer", "Senior AI Engineer"]
        ),
        seniority=_backed(Seniority.SENIOR),
        years_experience=_backed(7.0),
        preferred_locations=_backed(["Remote, US"]),
        remote_preference=_backed(RemotePreference.REMOTE),
        minimum_compensation=_derived(Compensation(amount=180000, currency="USD", period="year")),
        target_compensation=_derived(Compensation(amount=220000, currency="USD", period="year")),
        employment_preferences=_derived([EmploymentType.FULL_TIME, EmploymentType.CONTRACT]),
        industries=_derived(["healthcare", "AI", "B2B SaaS"]),
        preferred_company_stages=GroundedValue(value=None, provenance=Provenance.UNKNOWN),
        technologies=_backed(["Python", "PostgreSQL", "FastAPI"]),
        domains=_derived(["backend services", "healthcare technology"]),
        ai_experience=_backed("Current LLM workflow project; not multi-year production ML."),
        healthcare_experience=_backed("Healthcare operations software."),
        leadership_experience=GroundedValue(value=None, provenance=Provenance.UNKNOWN),
        summary=_derived("Senior backend engineer with healthcare and current AI project work."),
        unknown_fields=["preferred_company_stages", "leadership_experience"],
        demonstrated_categories=GroundedValue(
            value=demonstrated if rows else None,
            provenance=Provenance.DERIVED if rows else Provenance.UNKNOWN,
            evidence_ids=[item.id for item in rows] if rows else [],
            interpretation_notes="From stored evidence." if rows else None,
        ),
        unknown_categories=[EvidenceCategory.FRONTEND],
    )


def job_read(**overrides: object) -> JobRead:
    now = datetime(2026, 9, 21, tzinfo=UTC)
    values: dict[str, object] = {
        "id": UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
        "source": JobSource.MANUAL,
        "source_job_id": "eval-job",
        "company": "Helix Care",
        "title": "Senior Backend Engineer — Healthcare AI",
        "description": (
            "Build Python APIs for healthcare workflow automation and applied LLM tools."
        ),
        "location": "Remote - United States",
        "remote_policy": RemotePolicy.REMOTE,
        "employment_type": EmploymentType.FULL_TIME,
        "seniority": Seniority.SENIOR,
        "salary_min": 200000,
        "salary_max": 240000,
        "salary_currency": "USD",
        "job_url": "https://example.com/jobs/1",
        "application_url": "https://example.com/jobs/1/apply",
        "department": "Engineering",
        "posted_at": now,
        "discovered_at": now,
        "raw_data": {},
        "content_hash": "a" * 64,
        "is_duplicate_description": False,
        "duplicate_description_job_ids": [],
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return JobRead.model_validate(values)


def evaluation(**overrides: object) -> JobEvaluation:
    values: dict[str, object] = {
        "overall_score": 0,
        "technical_fit": 22,
        "domain_fit": 18,
        "product_fit": 12,
        "ai_relevance": 12,
        "seniority_fit": 9,
        "company_interest_fit": 8,
        "evidence_strength": 4,
        "recommendation": Recommendation.APPLY,
        "strengths": ["Python/PostgreSQL APIs cited in backend evidence."],
        "concerns": [],
        "missing_information": [],
        "supporting_evidence_ids": [EVIDENCE_BACKEND, EVIDENCE_HEALTHCARE, EVIDENCE_AI],
        "reasoning": (
            "Remote senior backend healthcare role matches cited backend and healthcare evidence."
        ),
    }
    values.update(overrides)
    return JobEvaluation.model_validate(values)


@dataclass
class StubEvaluationRunner:
    output: JobEvaluation
    last_input: str | None = None

    def evaluate(self, user_input: str, context: JobEvaluationContext) -> JobEvaluation:
        self.last_input = user_input
        del context
        return self.output
