"""Shared enumerations for the candidate profile subsystem."""

from enum import StrEnum


class Provenance(StrEnum):
    """How a profile field should be treated by AI agents."""

    EVIDENCE_BACKED = "evidence_backed"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class Seniority(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"
    DISTINGUISHED = "distinguished"


class RemotePreference(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    FLEXIBLE = "flexible"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    CONTRACT = "contract"
    PART_TIME = "part_time"


class CompanyStage(StrEnum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    EARLY = "early"
    GROWTH = "growth"
    LATE = "late"
    PUBLIC = "public"
    BOOTSTRAPPED = "bootstrapped"


class EvidenceCategory(StrEnum):
    DISTRIBUTED_SYSTEMS = "distributed_systems"
    BACKEND = "backend"
    FRONTEND = "frontend"
    HEALTHCARE = "healthcare"
    AI = "ai"
    LEADERSHIP = "leadership"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    ARCHITECTURE = "architecture"
    PRODUCT = "product"
    MENTORSHIP = "mentorship"
    SELF_REPORTED = "self_reported"


class EvidenceSource(StrEnum):
    RESUME = "resume"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    SELF_REPORTED = "self_reported"
    REFERENCE = "reference"
    OTHER = "other"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


PROFILE_GROUNDABLE_FIELDS: tuple[str, ...] = (
    "name",
    "target_titles",
    "seniority",
    "years_experience",
    "preferred_locations",
    "remote_preference",
    "minimum_compensation",
    "target_compensation",
    "employment_preferences",
    "industries",
    "preferred_company_stages",
    "technologies",
    "domains",
    "ai_experience",
    "healthcare_experience",
    "leadership_experience",
    "summary",
)
