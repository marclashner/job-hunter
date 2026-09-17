"""ORM models. Import every model module here so Alembic sees complete metadata."""

from app.db.base import Base
from app.models.candidate import CandidateEvidence, CandidateProfile
from app.models.enums import (
    PROFILE_GROUNDABLE_FIELDS,
    CompanyStage,
    ConfidenceLevel,
    EmploymentType,
    EvidenceCategory,
    EvidenceSource,
    Provenance,
    RemotePreference,
    Seniority,
)

__all__ = [
    "PROFILE_GROUNDABLE_FIELDS",
    "Base",
    "CandidateEvidence",
    "CandidateProfile",
    "CompanyStage",
    "ConfidenceLevel",
    "EmploymentType",
    "EvidenceCategory",
    "EvidenceSource",
    "Provenance",
    "RemotePreference",
    "Seniority",
]
