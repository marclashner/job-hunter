"""Deterministic offline rubric. Not an LLM. Only used when evaluation_mode=offline_rubric."""

from __future__ import annotations

import json
import re
from uuid import UUID

from app.agents.job_evaluation import (
    EvaluationProvenance,
    EvaluationRunResult,
    JobEvaluationContext,
)
from app.models.enums import EvaluationMode, Recommendation
from app.schemas.candidate import CandidateEvidenceRead
from app.schemas.evaluation import JobEvaluation
from app.schemas.job import JobRead
from app.scoring.hard_filters import HardFilterResult

_WORD = re.compile(r"[a-z0-9+]+")

OFFLINE_RUBRIC_PROVENANCE = EvaluationProvenance(
    evaluation_mode=EvaluationMode.OFFLINE_RUBRIC,
    model=None,
    provider="offline_rubric",
    llm_request_id=None,
    fallback_reason=None,
)


def evaluate_offline_rubric(
    job: JobRead,
    evidence: list[CandidateEvidenceRead],
    hard_filter: HardFilterResult,
) -> JobEvaluation:
    if not hard_filter.passed:
        rules = ", ".join(str(rule) for rule in hard_filter.failed_rules) or "unknown"
        return JobEvaluation.model_validate(
            {
                "overall_score": 0,
                "technical_fit": 0,
                "domain_fit": 0,
                "product_fit": 0,
                "ai_relevance": 0,
                "seniority_fit": 0,
                "company_interest_fit": 0,
                "evidence_strength": 0,
                "recommendation": Recommendation.REJECT,
                "strengths": [],
                "concerns": [f"Failed hard filter: {rules}"],
                "missing_information": list(hard_filter.missing_information),
                "supporting_evidence_ids": [],
                "reasoning": (
                    "Offline rubric (deterministic scoring, not a language-model run). "
                    f"Hard filters failed before scoring: {rules}."
                ),
            }
        )

    job_tokens = _tokens(job.title, job.description, job.company or "")
    cited: list[UUID] = []
    overlap = 0
    for item in evidence:
        shared = job_tokens & _tokens(
            item.claim,
            item.detailed_description,
            " ".join(item.technologies),
            " ".join(item.tags),
        )
        if shared:
            cited.append(item.id)
            overlap += len(shared)

    technical_fit = min(25, 6 + min(overlap, 19))
    domain_fit = min(20, 4 + min(overlap // 2, 16))
    product_fit = min(15, 3 + min(len(cited), 12))
    ai_tokens = job_tokens & {"ai", "llm", "ml", "agent", "agentic"}
    ai_relevance = min(15, 5 * len(ai_tokens))
    seniority_fit = 8 if (job.seniority or "") in {"senior", "staff", "principal"} else 5
    company_interest_fit = 6
    evidence_strength = min(5, len(cited))
    total = (
        technical_fit
        + domain_fit
        + product_fit
        + ai_relevance
        + seniority_fit
        + company_interest_fit
        + evidence_strength
    )
    recommendation = Recommendation.REVIEW
    if total >= 70 and cited:
        recommendation = Recommendation.APPLY
    elif total < 35:
        recommendation = Recommendation.REJECT
    return JobEvaluation.model_validate(
        {
            "overall_score": 0,
            "technical_fit": technical_fit,
            "domain_fit": domain_fit,
            "product_fit": product_fit,
            "ai_relevance": ai_relevance,
            "seniority_fit": seniority_fit,
            "company_interest_fit": company_interest_fit,
            "evidence_strength": evidence_strength,
            "recommendation": recommendation,
            "strengths": (["Offline rubric found overlapping evidence tokens."] if cited else []),
            "concerns": ([] if cited else ["Offline rubric found no overlapping evidence tokens."]),
            "missing_information": list(hard_filter.missing_information),
            "supporting_evidence_ids": cited[:8],
            "reasoning": (
                "Offline rubric (deterministic scoring, not a language-model run). "
                "Scores come from token overlap between the listing and CandidateEvidence "
                f"({overlap} overlapping tokens, {len(cited)} cited evidence records)."
            ),
        }
    )


class OfflineRubricEvaluationRunner:
    evaluation_mode: EvaluationMode = EvaluationMode.OFFLINE_RUBRIC

    def evaluate(self, user_input: str, context: JobEvaluationContext) -> EvaluationRunResult:
        payload = json.loads(user_input)
        job_data = dict(payload["job"])
        job_data.setdefault("raw_data", {})
        job = JobRead.model_validate(job_data)
        evaluation = evaluate_offline_rubric(job, list(context.evidence), context.hard_filter)
        return EvaluationRunResult(
            evaluation=evaluation,
            usage=None,
            provenance=OFFLINE_RUBRIC_PROVENANCE,
        )


def _tokens(*texts: str) -> set[str]:
    found: set[str] = set()
    for text in texts:
        found.update(token for token in _WORD.findall(text.lower()) if len(token) > 2)
    return found
