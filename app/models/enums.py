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
    EXPERIENCE = "experience"


class EvidenceSource(StrEnum):
    RESUME = "resume"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    SELF_REPORTED = "self_reported"
    REFERENCE = "reference"
    OTHER = "other"
    RESUME_AND_INTERVIEW_HISTORY = "resume_and_interview_history"
    INTERVIEW_HISTORY = "interview_history"
    RESUME_AND_SELF_REPORTED = "resume_and_self_reported"
    CURRENT_PROJECT = "current_project"
    DERIVED_FROM_RESUME_EVIDENCE = "derived_from_resume_evidence"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobSource(StrEnum):
    """Origin of an ingested listing. External adapters are not implemented yet."""

    MANUAL = "manual"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    COMPANY_SITE = "company_site"
    OTHER = "other"


class RemotePolicy(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Recommendation(StrEnum):
    APPLY = "apply"
    REVIEW = "review"
    REJECT = "reject"


class EvaluationMode(StrEnum):
    """How a stored evaluation was produced. Live and offline results must not be mixed."""

    LIVE_LLM = "live_llm"
    OFFLINE_RUBRIC = "offline_rubric"
    MOCK = "mock"


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
