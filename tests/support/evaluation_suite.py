"""At least 10 synthetic jobs for JobEvaluationAgent tests."""

from __future__ import annotations

from app.models.enums import EmploymentType, Recommendation, RemotePolicy, Seniority
from app.schemas.evaluation import JobEvaluation
from tests.support.evaluation import EVIDENCE_AI, EVIDENCE_BACKEND, EVIDENCE_HEALTHCARE, evaluation

SUITE: list[dict[str, object]] = [
    {
        "id": "healthcare-ai-backend",
        "job": {
            "title": "Senior Backend Engineer — Healthcare AI",
            "description": "Python APIs, PostgreSQL, healthcare workflows, applied LLM tooling.",
            "company": "Helix Care",
            "remote_policy": RemotePolicy.REMOTE,
            "location": "Remote - United States",
            "seniority": Seniority.SENIOR,
            "salary_min": 200000,
            "salary_max": 240000,
        },
        "expected_recommendation": Recommendation.APPLY,
        "output": evaluation(),
    },
    {
        "id": "frontend-adtech",
        "job": {
            "title": "Senior Frontend Engineer — AdTech",
            "description": "React advertising consoles. No backend ownership.",
            "company": "AdGrid",
            "remote_policy": RemotePolicy.REMOTE,
            "location": "Remote - United States",
        },
        "expected_recommendation": Recommendation.REVIEW,
        "output": evaluation(
            technical_fit=8,
            domain_fit=4,
            product_fit=6,
            ai_relevance=0,
            seniority_fit=8,
            company_interest_fit=3,
            evidence_strength=2,
            recommendation=Recommendation.REVIEW,
            strengths=["Senior IC title is in range."],
            concerns=["Frontend/AdTech is not backed by evidence; frontend is unknown."],
            supporting_evidence_ids=[EVIDENCE_BACKEND],
            reasoning="Weak domain/product fit; do not invent frontend experience.",
        ),
    },
    {
        "id": "staff-payments",
        "job": {
            "title": "Staff Engineer — Payments",
            "description": "Distributed payments platform. Python and PostgreSQL.",
            "company": "Payloop",
            "remote_policy": RemotePolicy.REMOTE,
            "seniority": Seniority.STAFF,
        },
        "expected_recommendation": Recommendation.REVIEW,
        "output": evaluation(
            technical_fit=18,
            domain_fit=8,
            product_fit=8,
            ai_relevance=2,
            seniority_fit=7,
            company_interest_fit=6,
            evidence_strength=3,
            recommendation=Recommendation.REVIEW,
            strengths=["Python/PostgreSQL match backend evidence."],
            concerns=["Payments domain is not evidenced as a specialty."],
            supporting_evidence_ids=[EVIDENCE_BACKEND],
            reasoning="Technical overlap with cited backend work; payments depth is unknown.",
        ),
    },
    {
        "id": "remote-healthcare",
        "job": {
            "title": "Senior SWE — Remote Healthcare",
            "description": "Full-stack optional; backend healthcare operations in Python.",
            "company": "ClinicOps",
            "remote_policy": RemotePolicy.REMOTE,
        },
        "expected_recommendation": Recommendation.APPLY,
        "output": evaluation(
            supporting_evidence_ids=[EVIDENCE_BACKEND, EVIDENCE_HEALTHCARE],
            reasoning=(
                "Remote healthcare backend work is supported by backend and healthcare evidence."
            ),
        ),
    },
    {
        "id": "crypto",
        "job": {
            "title": "Senior SWE — Crypto",
            "description": "Build cryptocurrency exchange matching engines.",
            "company": "CoinForge",
            "remote_policy": RemotePolicy.REMOTE,
        },
        "expected_recommendation": Recommendation.REVIEW,
        "output": evaluation(
            technical_fit=10,
            domain_fit=2,
            product_fit=4,
            ai_relevance=0,
            seniority_fit=8,
            company_interest_fit=2,
            evidence_strength=1,
            recommendation=Recommendation.REVIEW,
            strengths=["Senior SWE title."],
            concerns=["Crypto is outside evidenced industries."],
            supporting_evidence_ids=[EVIDENCE_BACKEND],
            reasoning="Do not treat crypto as a match without evidence.",
        ),
    },
    {
        "id": "onsite-sf",
        "job": {
            "title": "Senior SWE — Onsite SF",
            "description": "Python services. Five days in San Francisco.",
            "location": "San Francisco, CA",
            "remote_policy": RemotePolicy.ONSITE,
        },
        "expected_recommendation": Recommendation.REJECT,
        "output": evaluation(
            recommendation=Recommendation.APPLY,
            reasoning="Agent incorrectly tried to apply; hard filter must force reject.",
        ),
    },
    {
        "id": "low-salary",
        "job": {
            "title": "Senior SWE — $120k",
            "description": "Python backend. Compensation max 120000 USD.",
            "salary_min": 110000,
            "salary_max": 120000,
            "remote_policy": RemotePolicy.REMOTE,
        },
        "expected_recommendation": Recommendation.REJECT,
        "output": evaluation(
            recommendation=Recommendation.REVIEW,
            reasoning="Pay is below the stored minimum; hard filter rejects.",
        ),
    },
    {
        "id": "ai-infrastructure",
        "job": {
            "title": "Senior SWE — AI Infrastructure",
            "description": "Platform for LLM workflows, Python, evaluation harnesses.",
            "company": "Stackline AI",
            "remote_policy": RemotePolicy.REMOTE,
        },
        "expected_recommendation": Recommendation.APPLY,
        "output": evaluation(
            supporting_evidence_ids=[EVIDENCE_BACKEND, EVIDENCE_AI],
            reasoning="AI infrastructure overlaps cited current LLM project and backend evidence.",
        ),
    },
    {
        "id": "engineering-manager",
        "job": {
            "title": "Engineering Manager — Healthcare",
            "description": "People management for a healthcare engineering org.",
            "remote_policy": RemotePolicy.REMOTE,
        },
        "expected_recommendation": Recommendation.REJECT,
        "output": evaluation(
            recommendation=Recommendation.REVIEW,
            reasoning="Management role fails target-title hard filter.",
        ),
    },
    {
        "id": "missing-salary",
        "job": {
            "title": "Senior Backend Engineer",
            "description": "Python healthcare APIs. Compensation not listed.",
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "remote_policy": RemotePolicy.REMOTE,
        },
        "expected_recommendation": Recommendation.REVIEW,
        "output": evaluation(
            recommendation=Recommendation.REVIEW,
            missing_information=[],
            supporting_evidence_ids=[EVIDENCE_BACKEND, EVIDENCE_HEALTHCARE],
            reasoning="Fit is promising but salary is unknown so certainty is not claimed.",
        ),
    },
    {
        "id": "misleading-ai-buzzwords",
        "job": {
            "title": "Senior Software Engineer",
            "description": (
                "Join our AI-powered revolution! You will run outbound sales sequences "
                "and update Salesforce. No software engineering required despite the title."
            ),
            "remote_policy": RemotePolicy.REMOTE,
        },
        "expected_recommendation": Recommendation.REJECT,
        "output": evaluation(
            technical_fit=2,
            domain_fit=1,
            product_fit=1,
            ai_relevance=0,
            seniority_fit=4,
            company_interest_fit=1,
            evidence_strength=1,
            recommendation=Recommendation.REJECT,
            strengths=[],
            concerns=["Description is sales work marketed as AI/SWE."],
            supporting_evidence_ids=[EVIDENCE_BACKEND],
            reasoning=(
                "Misleading AI/SWE branding; actual work is sales, not evidenced engineering."
            ),
        ),
    },
    {
        "id": "junior-support",
        "job": {
            "title": "Junior Support Engineer",
            "description": "Password resets and ticket triage.",
            "seniority": Seniority.JUNIOR,
            "remote_policy": RemotePolicy.REMOTE,
            "employment_type": EmploymentType.FULL_TIME,
        },
        "expected_recommendation": Recommendation.REJECT,
        "output": evaluation(
            recommendation=Recommendation.APPLY,
            reasoning="Hard filter seniority floor must reject junior support.",
        ),
    },
]


def suite_evaluation(case: dict[str, object]) -> JobEvaluation:
    output = case["output"]
    assert isinstance(output, JobEvaluation)
    return output
