"""JobEvaluationAgent unit tests. The OpenAI API is not called."""

from uuid import uuid4

import pytest

from app.agents.grounding import EvaluationGroundingError, ground_evaluation
from app.agents.job_evaluation import (
    build_evaluation_input,
    build_job_evaluation_agent,
    job_evaluation_model_settings,
)
from app.config import get_settings
from app.models.enums import EmploymentType, Recommendation, RemotePreference, Seniority
from app.schemas.candidate import Compensation
from app.scoring.hard_filters import HardFilterCandidate, evaluate_hard_filters
from tests.support.evaluation import (
    EVIDENCE_BACKEND,
    evaluation,
    job_read,
    synthetic_evidence,
    synthetic_profile,
)
from tests.support.evaluation_suite import SUITE, suite_evaluation


def _candidate() -> HardFilterCandidate:
    return HardFilterCandidate(
        target_titles=["Senior Software Engineer", "Senior Backend Engineer", "Senior AI Engineer"],
        seniority=Seniority.SENIOR,
        preferred_locations=["Remote, US"],
        remote_preference=RemotePreference.REMOTE,
        employment_preferences=[EmploymentType.FULL_TIME, EmploymentType.CONTRACT],
        minimum_compensation=Compensation(amount=180000, currency="USD", period="year"),
    )


def test_agent_uses_low_temperature_and_seed_for_classification(
    clear_settings_cache: None,
) -> None:
    settings = get_settings()
    model_settings = job_evaluation_model_settings(settings)
    assert model_settings.temperature == 0
    assert model_settings.top_p == 1
    assert not model_settings.extra_args
    agent = build_job_evaluation_agent(settings)
    assert agent.name == "JobEvaluationAgent"
    assert agent.output_type is not None


def test_strong_match_keeps_apply_and_citations() -> None:
    evidence = synthetic_evidence()
    result = ground_evaluation(
        evaluation(),
        allowed_evidence_ids={item.id for item in evidence},
        evidence=evidence,
        hard_filter=evaluate_hard_filters(job_read(), _candidate()),
    )
    assert result.recommendation is Recommendation.APPLY
    assert EVIDENCE_BACKEND in result.supporting_evidence_ids
    assert result.overall_score == (
        result.technical_fit
        + result.domain_fit
        + result.product_fit
        + result.ai_relevance
        + result.seniority_fit
        + result.company_interest_fit
        + result.evidence_strength
    )


def test_weak_match_stays_review() -> None:
    evidence = synthetic_evidence()
    weak = evaluation(
        technical_fit=6,
        domain_fit=3,
        product_fit=3,
        ai_relevance=0,
        seniority_fit=7,
        company_interest_fit=2,
        evidence_strength=1,
        recommendation=Recommendation.REVIEW,
        strengths=["Title is senior."],
        concerns=["AdTech frontend is unevidenced."],
        supporting_evidence_ids=[EVIDENCE_BACKEND],
        reasoning="Weak overlap with cited backend work only.",
    )
    result = ground_evaluation(
        weak,
        allowed_evidence_ids={item.id for item in evidence},
        evidence=evidence,
        hard_filter=evaluate_hard_filters(
            job_read(title="Senior Frontend Engineer — AdTech"), _candidate()
        ),
    )
    assert result.recommendation is Recommendation.REVIEW
    assert result.overall_score < 40


def test_missing_salary_is_recorded_and_does_not_force_reject() -> None:
    evidence = synthetic_evidence()
    job = job_read(salary_min=None, salary_max=None, salary_currency=None)
    hard_filter = evaluate_hard_filters(job, _candidate())
    assert hard_filter.salary_unknown is True
    result = ground_evaluation(
        evaluation(recommendation=Recommendation.REVIEW, missing_information=[]),
        allowed_evidence_ids={item.id for item in evidence},
        evidence=evidence,
        hard_filter=hard_filter,
    )
    assert result.recommendation is Recommendation.REVIEW
    assert "job_salary" in result.missing_information
    prompt = build_evaluation_input(job, synthetic_profile(), evidence, hard_filter)
    assert "salary_unknown" in prompt
    assert '"salary_min": null' in prompt


def test_missing_candidate_evidence_demotes_apply_and_clears_citations() -> None:
    hard_filter = evaluate_hard_filters(job_read(), _candidate())
    result = ground_evaluation(
        evaluation(
            recommendation=Recommendation.APPLY,
            evidence_strength=5,
            supporting_evidence_ids=[],
        ),
        allowed_evidence_ids=set(),
        evidence=[],
        hard_filter=hard_filter,
    )
    assert result.recommendation is Recommendation.REVIEW
    assert result.evidence_strength == 0
    assert result.supporting_evidence_ids == []
    assert "candidate_evidence" in result.missing_information


def test_misleading_job_description_is_in_the_agent_payload() -> None:
    description = (
        "AI-powered revolution. You will run outbound sales sequences in Salesforce. "
        "No software engineering required."
    )
    job = job_read(title="Senior Software Engineer", description=description)
    hard_filter = evaluate_hard_filters(job, _candidate())
    prompt = build_evaluation_input(job, synthetic_profile(), synthetic_evidence(), hard_filter)
    assert "outbound sales sequences" in prompt
    assert "No software engineering required" in prompt
    result = ground_evaluation(
        evaluation(
            technical_fit=2,
            domain_fit=1,
            product_fit=1,
            ai_relevance=0,
            seniority_fit=4,
            company_interest_fit=1,
            evidence_strength=1,
            recommendation=Recommendation.REJECT,
            concerns=["Sales work branded as AI engineering."],
            supporting_evidence_ids=[EVIDENCE_BACKEND],
            reasoning="Do not treat AI slogans as the real job.",
        ),
        allowed_evidence_ids={EVIDENCE_BACKEND},
        evidence=synthetic_evidence(),
        hard_filter=hard_filter,
    )
    assert result.recommendation is Recommendation.REJECT
    assert any(
        "sales" in item.lower() or "slogan" in result.reasoning.lower() for item in result.concerns
    ) or ("slogan" in result.reasoning.lower() or "sales" in result.reasoning.lower())


def test_unsupported_candidate_skill_is_rejected() -> None:
    evidence = synthetic_evidence()
    with pytest.raises(EvaluationGroundingError, match="cobol"):
        ground_evaluation(
            evaluation(
                strengths=["The candidate has production COBOL experience."],
                supporting_evidence_ids=[EVIDENCE_BACKEND],
                reasoning="COBOL is a fabricated strength.",
            ),
            allowed_evidence_ids={item.id for item in evidence},
            evidence=evidence,
            hard_filter=evaluate_hard_filters(job_read(), _candidate()),
        )


def test_unknown_evidence_id_is_rejected() -> None:
    evidence = synthetic_evidence()
    with pytest.raises(EvaluationGroundingError, match="supporting_evidence_ids"):
        ground_evaluation(
            evaluation(supporting_evidence_ids=[uuid4()]),
            allowed_evidence_ids={item.id for item in evidence},
            evidence=evidence,
            hard_filter=evaluate_hard_filters(job_read(), _candidate()),
        )


@pytest.mark.parametrize("case", SUITE, ids=lambda case: str(case["id"]))
def test_evaluation_fixture_suite(case: dict[str, object]) -> None:
    job_overrides = case["job"]
    assert isinstance(job_overrides, dict)
    job = job_read(**job_overrides)
    evidence = synthetic_evidence()
    hard_filter = evaluate_hard_filters(job, _candidate())
    prompt = build_evaluation_input(job, synthetic_profile(evidence), evidence, hard_filter)
    assert job.title in prompt
    assert job.description[:40] in prompt
    grounded = ground_evaluation(
        suite_evaluation(case),
        allowed_evidence_ids={item.id for item in evidence},
        evidence=evidence,
        hard_filter=hard_filter,
    )
    assert grounded.recommendation is case["expected_recommendation"]
    assert "job_salary" in grounded.missing_information or not hard_filter.salary_unknown
