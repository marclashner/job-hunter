"""Optional live OpenAI run. Skipped without OPENAI_API_KEY. Not part of CI determinism."""

import os

import pytest

from app.agents.job_evaluation import (
    JobEvaluationContext,
    OpenAIAgentsEvaluationRunner,
    build_evaluation_input,
)
from app.config import get_settings
from app.models.enums import EmploymentType, RemotePreference, Seniority
from app.schemas.candidate import Compensation
from app.schemas.evaluation import JobEvaluation
from app.scoring.hard_filters import HardFilterCandidate, evaluate_hard_filters
from tests.support.evaluation import job_read, synthetic_evidence, synthetic_profile


@pytest.mark.live_openai
def test_live_openai_evaluation_returns_schema(clear_settings_cache: None) -> None:
    if os.environ.get("RUN_LIVE_OPENAI") != "1":
        pytest.skip("Set RUN_LIVE_OPENAI=1 and OPENAI_API_KEY to call the model")
    if not os.environ.get("OPENAI_API_KEY") and not get_settings().openai_api_key:
        pytest.skip("OPENAI_API_KEY is not set")
    evidence = synthetic_evidence()
    job = job_read()
    hard_filter = evaluate_hard_filters(
        job,
        HardFilterCandidate(
            target_titles=["Senior Backend Engineer"],
            seniority=Seniority.SENIOR,
            preferred_locations=["Remote, US"],
            remote_preference=RemotePreference.REMOTE,
            employment_preferences=[EmploymentType.FULL_TIME],
            minimum_compensation=Compensation(amount=180000, currency="USD"),
        ),
    )
    context = JobEvaluationContext(
        allowed_evidence_ids=frozenset(item.id for item in evidence),
        evidence=tuple(evidence),
        hard_filter=hard_filter,
    )
    prompt = build_evaluation_input(job, synthetic_profile(evidence), evidence, hard_filter)
    output = OpenAIAgentsEvaluationRunner().evaluate(prompt, context)
    assert isinstance(output, JobEvaluation)
    assert output.reasoning
