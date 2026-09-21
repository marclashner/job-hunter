"""ORM models. Import every model module here so Alembic sees complete metadata."""

from app.db.base import Base
from app.models.candidate import CandidateEvidence, CandidateProfile
from app.models.enums import (
    PROFILE_GROUNDABLE_FIELDS,
    CompanyStage,
    ConfidenceLevel,
    EmploymentType,
    EvaluationMode,
    EvidenceCategory,
    EvidenceSource,
    HumanDecision,
    JobSource,
    Provenance,
    Recommendation,
    RemotePolicy,
    RemotePreference,
    Seniority,
)
from app.models.evaluation import JobEvaluationRecord
from app.models.job import Job

__all__ = [
    "PROFILE_GROUNDABLE_FIELDS",
    "Base",
    "CandidateEvidence",
    "CandidateProfile",
    "CompanyStage",
    "ConfidenceLevel",
    "EmploymentType",
    "EvaluationMode",
    "EvidenceCategory",
    "EvidenceSource",
    "HumanDecision",
    "Job",
    "JobEvaluationRecord",
    "JobSource",
    "Provenance",
    "Recommendation",
    "RemotePolicy",
    "RemotePreference",
    "Seniority",
]
