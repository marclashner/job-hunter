"""Deterministic grounding for JobEvaluationAgent output.

The model is not trusted to cite evidence correctly. Unknown IDs and
un-evidenced skill claims in strengths are rejected before persistence.
"""

from __future__ import annotations

import re
from uuid import UUID

from app.models.enums import Recommendation
from app.schemas.candidate import CandidateEvidenceRead
from app.schemas.evaluation import JobEvaluation
from app.scoring.hard_filters import HardFilterResult

_SKILL_TOKENS_REQUIRING_EVIDENCE = frozenset(
    {
        "cobol",
        "fortran",
        "haskell",
        "elixir",
        "erlang",
        "perl",
        "php",
        "ruby",
        "rust",
        "scala",
        "swift",
        "kotlin",
        "salesforce",
        "sap",
        "mainframe",
        "hadoop",
        "pytorch",
        "tensorflow",
    }
)


class EvaluationGroundingError(ValueError):
    """Raised when the model cites missing evidence or invents experience."""


def ground_evaluation(
    evaluation: JobEvaluation,
    *,
    allowed_evidence_ids: set[UUID],
    evidence: list[CandidateEvidenceRead],
    hard_filter: HardFilterResult,
) -> JobEvaluation:
    unknown_ids = [
        item for item in evaluation.supporting_evidence_ids if item not in allowed_evidence_ids
    ]
    if unknown_ids and evidence:
        raise EvaluationGroundingError(
            "supporting_evidence_ids contains IDs that are not in CandidateEvidence: "
            + ", ".join(str(item) for item in unknown_ids)
        )

    blob = _evidence_blob(evidence)
    invented = _unsupported_skill_claims(evaluation.strengths, blob)
    invented.extend(_unsupported_skill_claims([evaluation.reasoning], blob))
    if invented:
        raise EvaluationGroundingError(
            "evaluation claims candidate skills that are not in CandidateEvidence: "
            + ", ".join(sorted(set(invented)))
        )

    missing = list(
        dict.fromkeys([*evaluation.missing_information, *hard_filter.missing_information])
    )
    if hard_filter.salary_unknown and "job_salary" not in missing:
        missing.append("job_salary")

    recommendation = evaluation.recommendation
    evidence_strength = evaluation.evidence_strength
    cited = list(evaluation.supporting_evidence_ids)
    if not evidence:
        evidence_strength = 0
        cited = []
        if recommendation is Recommendation.APPLY:
            recommendation = Recommendation.REVIEW
        if "candidate_evidence" not in missing:
            missing.append("candidate_evidence")
    if not hard_filter.passed:
        recommendation = Recommendation.REJECT

    return evaluation.model_copy(
        update={
            "recommendation": recommendation,
            "evidence_strength": evidence_strength,
            "supporting_evidence_ids": cited,
            "missing_information": missing,
        }
    )


def _evidence_blob(evidence: list[CandidateEvidenceRead]) -> str:
    parts: list[str] = []
    for item in evidence:
        parts.append(item.claim)
        parts.append(item.detailed_description)
        parts.extend(item.technologies)
        parts.extend(item.tags)
    return " ".join(parts).lower()


def _unsupported_skill_claims(texts: list[str], evidence_blob: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        lowered = text.lower()
        for token in _SKILL_TOKENS_REQUIRING_EVIDENCE:
            if re.search(rf"\b{re.escape(token)}\b", lowered) and token not in evidence_blob:
                found.append(token)
    return found
