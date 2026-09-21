"""JobEvaluationAgent: decide whether a listing is worth the candidate's time."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from agents import (
    Agent,
    GuardrailFunctionOutput,
    ModelSettings,
    OutputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    output_guardrail,
    set_tracing_disabled,
)
from app.agents.grounding import EvaluationGroundingError, ground_evaluation
from app.config import Settings, get_settings
from app.schemas.candidate import CandidateEvidenceRead, CandidateProfileRead
from app.schemas.evaluation import JobEvaluation
from app.schemas.job import JobRead
from app.scoring.hard_filters import HardFilterResult

set_tracing_disabled(True)

INSTRUCTIONS = """
You are JobEvaluationAgent for an autonomous job-search system.

Your ONLY job is to judge whether a job listing is worth this candidate's time.
You do not write applications, cover letters, or outreach.
You do not submit applications.
You do not negotiate or contact employers.

Hard rules:
- Never invent candidate qualifications, employers, titles, stack, metrics,
  or domain experience.
- Never infer experience that is not in CandidateEvidence. Absence of evidence
  is unknown, not a gap you may fill with a story.
- When you state that the candidate has done something, cite the evidence UUID
  in supporting_evidence_ids. If you cannot cite an allowed ID, do not claim it.
- Preferences (compensation, remote, target titles) are not proof of skill.
- Do not use or mention protected characteristics (age, race, sex, gender,
  religion, disability, national origin, pregnancy, veteran status, and similar)
  even if a listing alludes to them.
- Do not claim certainty when information is missing. Put gaps in
  missing_information. Unlisted salary is not a rejection by itself.
- Treat misleading or buzzword-heavy descriptions as a concern. Score the real
  requirements, not slogans like "AI-powered" when the work is unrelated.
- HardFilterResult is deterministic eligibility. If passed is false,
  recommendation must be reject. If salary_unknown or other missing_information
  flags are set, do not pretend those fields are known.
- Recommend apply, review, or reject. apply requires cited evidence of relevant
  work. review is for incomplete data or mixed fit. reject is for clear
  mismatches or failed hard filters.

Score components (integers; overall_score must equal their sum):
- technical_fit 0-25
- domain_fit 0-20
- product_fit 0-15
- ai_relevance 0-15
- seniority_fit 0-10
- company_interest_fit 0-10
- evidence_strength 0-5
""".strip()


@dataclass(frozen=True)
class JobEvaluationContext:
    allowed_evidence_ids: frozenset[UUID]
    evidence: tuple[CandidateEvidenceRead, ...]
    hard_filter: HardFilterResult


class JobEvaluationRunner(Protocol):
    """Production uses the OpenAI Agents SDK; tests inject a stub."""

    def evaluate(self, user_input: str, context: JobEvaluationContext) -> JobEvaluation: ...


class EvaluationConfigurationError(RuntimeError):
    """Raised when the OpenAI client cannot run (missing key, etc.)."""


class EvaluationAgentError(RuntimeError):
    """Raised when the agent run fails after retries."""


@output_guardrail
def evidence_citation_guardrail(
    ctx: RunContextWrapper[JobEvaluationContext],
    agent: Agent[JobEvaluationContext],
    output: JobEvaluation,
) -> GuardrailFunctionOutput:
    del agent
    try:
        ground_evaluation(
            output,
            allowed_evidence_ids=set(ctx.context.allowed_evidence_ids),
            evidence=list(ctx.context.evidence),
            hard_filter=ctx.context.hard_filter,
        )
    except EvaluationGroundingError as exc:
        return GuardrailFunctionOutput(output_info=str(exc), tripwire_triggered=True)
    return GuardrailFunctionOutput(output_info="grounded", tripwire_triggered=False)


def job_evaluation_model_settings(settings: Settings) -> ModelSettings:
    """Low temperature and a seed for structured classification. Seed is best-effort."""

    return ModelSettings(
        temperature=settings.openai_evaluation_temperature,
        top_p=1.0,
    )


def build_job_evaluation_agent(settings: Settings | None = None) -> Agent[JobEvaluationContext]:
    cfg = settings or get_settings()
    return Agent(
        name="JobEvaluationAgent",
        instructions=INSTRUCTIONS,
        model=cfg.openai_model,
        model_settings=job_evaluation_model_settings(cfg),
        output_type=JobEvaluation,
        output_guardrails=[evidence_citation_guardrail],
    )


def build_evaluation_input(
    job: JobRead,
    profile: CandidateProfileRead,
    evidence: list[CandidateEvidenceRead],
    hard_filter: HardFilterResult,
) -> str:
    payload = {
        "job": job.model_dump(mode="json", exclude={"raw_data"}),
        "candidate_profile": profile.model_dump(mode="json"),
        "candidate_evidence": [item.model_dump(mode="json") for item in evidence],
        "hard_filter": hard_filter.model_dump(mode="json"),
        "allowed_evidence_ids": [str(item.id) for item in evidence],
        "task": "Return a JobEvaluation. Cite only allowed_evidence_ids for experience claims.",
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


class OpenAIAgentsEvaluationRunner:
    """Runs JobEvaluationAgent via the OpenAI Agents SDK."""

    def evaluate(self, user_input: str, context: JobEvaluationContext) -> JobEvaluation:
        settings = get_settings()
        if not settings.openai_api_key:
            raise EvaluationConfigurationError(
                "OPENAI_API_KEY is not set. Add it to the environment to run JobEvaluationAgent."
            )
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        agent = build_job_evaluation_agent(settings)
        try:
            result = Runner.run_sync(
                agent,
                user_input,
                context=context,
                max_turns=1,
            )
        except OutputGuardrailTripwireTriggered as exc:
            raise EvaluationGroundingError("agent output failed evidence grounding") from exc
        except Exception as exc:
            raise EvaluationAgentError("JobEvaluationAgent run failed") from exc
        output = result.final_output
        if isinstance(output, JobEvaluation):
            return output
        return JobEvaluation.model_validate(output)
