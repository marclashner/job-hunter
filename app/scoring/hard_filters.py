"""Deterministic hard filters. Missing job fields never cause a failure by themselves."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.candidate import CandidateProfile
from app.models.enums import EmploymentType, RemotePolicy, RemotePreference, Seniority
from app.models.job import Job
from app.schemas.candidate import Compensation
from app.schemas.job import JobRead

_WORD = re.compile(r"[a-z0-9+]+")
_SENIORITY_RANK: dict[Seniority, int] = {
    Seniority.JUNIOR: 0,
    Seniority.MID: 1,
    Seniority.SENIOR: 2,
    Seniority.STAFF: 3,
    Seniority.PRINCIPAL: 4,
    Seniority.DISTINGUISHED: 5,
}
_SOFTWARE_IC_TOKENS = frozenset(
    {
        "ai",
        "backend",
        "developer",
        "devops",
        "engineer",
        "engineering",
        "founding",
        "frontend",
        "fullstack",
        "infrastructure",
        "ml",
        "platform",
        "programmer",
        "software",
        "sre",
        "swe",
    }
)
_MANAGEMENT_TOKENS = frozenset({"chief", "director", "head", "manager", "vp"})
_DESIGN_TOKENS = frozenset({"designer", "ux", "ui"})
_SPECIALIZATIONS = {
    "frontend": frozenset({"frontend", "ui"}),
    "backend": frozenset({"backend"}),
    "fullstack": frozenset({"fullstack"}),
    "ai": frozenset({"ai", "ml", "llm"}),
    "mobile": frozenset({"ios", "android", "mobile"}),
    "platform": frozenset({"platform", "infrastructure", "sre", "devops"}),
    "data": frozenset({"data", "analytics"}),
}
_INDUSTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "crypto": ("crypto", "cryptocurrency", "bitcoin", "web3", "defi", "nft", "blockchain"),
    "adtech": ("adtech", "ad tech", "advertising"),
    "healthcare": ("healthcare", "healthtech", "health tech", "clinical", "hospital", "hipaa"),
    "payments": ("payments", "fintech", "billing"),
    "gambling": ("gambling", "casino", "sportsbook"),
    "games": ("game studio", "video game", "gaming"),
}


class HardFilterRule(StrEnum):
    UNACCEPTABLE_LOCATION = "unacceptable_location"
    UNACCEPTABLE_ONSITE_REQUIREMENT = "unacceptable_onsite_requirement"
    BELOW_MINIMUM_SENIORITY = "below_minimum_seniority"
    UNACCEPTABLE_EMPLOYMENT_TYPE = "unacceptable_employment_type"
    BELOW_MINIMUM_COMPENSATION = "below_minimum_compensation"
    TARGET_ROLE_MISMATCH = "target_role_mismatch"
    EXCLUDED_INDUSTRY = "excluded_industry"


class JobFilterInput(BaseModel):
    """Job fields the hard filter is allowed to read."""

    title: str
    description: str = ""
    company: str = ""
    department: str | None = None
    location: str | None = None
    remote_policy: RemotePolicy | None = None
    employment_type: EmploymentType | None = None
    seniority: Seniority | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None

    @classmethod
    def from_job(cls, job: Job | JobRead | JobFilterInput) -> JobFilterInput:
        if isinstance(job, JobFilterInput):
            return job
        if isinstance(job, JobRead):
            return cls(
                title=job.title,
                description=job.description,
                company=job.company,
                department=job.department,
                location=job.location,
                remote_policy=job.remote_policy,
                employment_type=job.employment_type,
                seniority=job.seniority,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
            )
        return cls(
            title=job.title,
            description=job.description,
            company=job.company,
            department=job.department,
            location=job.location,
            remote_policy=RemotePolicy(job.remote_policy) if job.remote_policy else None,
            employment_type=EmploymentType(job.employment_type) if job.employment_type else None,
            seniority=Seniority(job.seniority) if job.seniority else None,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            salary_currency=job.salary_currency,
        )


class HardFilterCandidate(BaseModel):
    """Candidate constraints used by hard filters. Empty collections mean 'not configured'."""

    target_titles: list[str] = Field(default_factory=list)
    seniority: Seniority | None = None
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: RemotePreference | None = None
    employment_preferences: list[EmploymentType] = Field(default_factory=list)
    minimum_compensation: Compensation | None = None
    excluded_industries: list[str] = Field(default_factory=list)

    @classmethod
    def from_profile(cls, profile: CandidateProfile | HardFilterCandidate) -> HardFilterCandidate:
        if isinstance(profile, HardFilterCandidate):
            return profile
        compensation = _compensation(profile.minimum_compensation)
        seniority = Seniority(profile.seniority) if profile.seniority else None
        remote = RemotePreference(profile.remote_preference) if profile.remote_preference else None
        employment = [EmploymentType(item) for item in profile.employment_preferences]
        excluded = _string_list(getattr(profile, "excluded_industries", None))
        return cls(
            target_titles=list(profile.target_titles or []),
            seniority=seniority,
            preferred_locations=list(profile.preferred_locations or []),
            remote_preference=remote,
            employment_preferences=employment,
            minimum_compensation=compensation,
            excluded_industries=excluded,
        )


class HardFilterResult(BaseModel):
    passed: bool
    failed_rules: list[str]
    warnings: list[str]
    missing_information: list[str]
    salary_unknown: bool = False


def evaluate_hard_filters(
    job: Job | JobRead | JobFilterInput,
    profile: CandidateProfile | HardFilterCandidate,
) -> HardFilterResult:
    """Apply deterministic knock-out rules. Unknown job data is recorded, not rejected."""

    listing = JobFilterInput.from_job(job)
    candidate = HardFilterCandidate.from_profile(profile)
    failed: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    salary_unknown = listing.salary_min is None and listing.salary_max is None
    if salary_unknown:
        missing.append("job_salary")

    _apply_onsite(listing, candidate, failed, missing)
    _apply_location(listing, candidate, failed, warnings, missing)
    _apply_seniority(listing, candidate, failed, missing)
    _apply_employment(listing, candidate, failed, missing)
    _apply_compensation(listing, candidate, failed, warnings, salary_unknown)
    _apply_title(listing, candidate, failed, warnings, missing)
    _apply_industry(listing, candidate, failed, missing)

    return HardFilterResult(
        passed=not failed,
        failed_rules=failed,
        warnings=warnings,
        missing_information=missing,
        salary_unknown=salary_unknown,
    )


def _apply_onsite(
    job: JobFilterInput,
    candidate: HardFilterCandidate,
    failed: list[str],
    missing: list[str],
) -> None:
    preference = candidate.remote_preference
    if preference is None:
        return
    if job.remote_policy is None or job.remote_policy is RemotePolicy.UNKNOWN:
        if preference is RemotePreference.REMOTE:
            missing.append("job_remote_policy")
        return
    requires_onsite = job.remote_policy in {RemotePolicy.ONSITE, RemotePolicy.HYBRID}
    if requires_onsite and preference is RemotePreference.REMOTE:
        failed.append(HardFilterRule.UNACCEPTABLE_ONSITE_REQUIREMENT.value)


def _apply_location(
    job: JobFilterInput,
    candidate: HardFilterCandidate,
    failed: list[str],
    warnings: list[str],
    missing: list[str],
) -> None:
    location = (job.location or "").strip()
    if _contradictory_location(job.remote_policy, location):
        warnings.append("contradictory_location_information")
    if not candidate.preferred_locations:
        return
    if not location:
        missing.append("job_location")
        return
    if job.remote_policy is RemotePolicy.REMOTE:
        return
    if job.remote_policy is None or job.remote_policy is RemotePolicy.UNKNOWN:
        if "job_remote_policy" not in missing:
            missing.append("job_remote_policy")
        return
    if not _location_matches_preferred(location, candidate.preferred_locations):
        failed.append(HardFilterRule.UNACCEPTABLE_LOCATION.value)


def _apply_seniority(
    job: JobFilterInput,
    candidate: HardFilterCandidate,
    failed: list[str],
    missing: list[str],
) -> None:
    if candidate.seniority is None:
        return
    if job.seniority is None:
        missing.append("job_seniority")
        return
    if _SENIORITY_RANK[job.seniority] < _SENIORITY_RANK[candidate.seniority]:
        failed.append(HardFilterRule.BELOW_MINIMUM_SENIORITY.value)


def _apply_employment(
    job: JobFilterInput,
    candidate: HardFilterCandidate,
    failed: list[str],
    missing: list[str],
) -> None:
    if not candidate.employment_preferences:
        return
    if job.employment_type is None:
        missing.append("job_employment_type")
        return
    if job.employment_type not in candidate.employment_preferences:
        failed.append(HardFilterRule.UNACCEPTABLE_EMPLOYMENT_TYPE.value)


def _apply_compensation(
    job: JobFilterInput,
    candidate: HardFilterCandidate,
    failed: list[str],
    warnings: list[str],
    salary_unknown: bool,
) -> None:
    minimum = candidate.minimum_compensation
    if minimum is None or salary_unknown:
        return
    if job.salary_currency and job.salary_currency.upper() != minimum.currency.upper():
        warnings.append("compensation_currency_mismatch")
        return
    floor = _annual_amount(minimum)
    if job.salary_max is not None:
        if job.salary_max < floor:
            failed.append(HardFilterRule.BELOW_MINIMUM_COMPENSATION.value)
        return
    if job.salary_min is not None and job.salary_min < floor:
        warnings.append("salary_ceiling_unknown")


def _apply_title(
    job: JobFilterInput,
    candidate: HardFilterCandidate,
    failed: list[str],
    warnings: list[str],
    missing: list[str],
) -> None:
    if not candidate.target_titles:
        missing.append("candidate_target_titles")
        return
    job_family = _role_family(job.title)
    if job_family == "unknown":
        warnings.append("title_unclassified")
        missing.append("job_role_family")
        return
    candidate_families = {_role_family(title) for title in candidate.target_titles}
    candidate_families.discard("unknown")
    if candidate_families and job_family not in candidate_families:
        failed.append(HardFilterRule.TARGET_ROLE_MISMATCH.value)
        return
    if job_family != "software_ic":
        return
    job_specs = _specializations(job.title)
    candidate_specs = set()
    candidate_generic = False
    for title in candidate.target_titles:
        specs = _specializations(title)
        if specs:
            candidate_specs |= specs
        elif _role_family(title) == "software_ic":
            candidate_generic = True
    if candidate_generic or not job_specs or not candidate_specs:
        return
    if "fullstack" in candidate_specs and job_specs & {"frontend", "backend"}:
        return
    if job_specs.isdisjoint(candidate_specs):
        failed.append(HardFilterRule.TARGET_ROLE_MISMATCH.value)


def _apply_industry(
    job: JobFilterInput,
    candidate: HardFilterCandidate,
    failed: list[str],
    missing: list[str],
) -> None:
    excluded = [_normalize_key(item) for item in candidate.excluded_industries if item.strip()]
    if not excluded:
        return
    blob = " ".join(
        part for part in (job.title, job.company, job.department or "", job.description) if part
    ).lower()
    detected = _detect_industries(blob)
    if not detected:
        missing.append("job_industry")
        return
    if any(item in detected or item in blob for item in excluded):
        failed.append(HardFilterRule.EXCLUDED_INDUSTRY.value)


def _contradictory_location(policy: RemotePolicy | None, location: str) -> bool:
    lowered = location.lower()
    mentions_remote = "remote" in lowered
    mentions_onsite = any(token in lowered for token in ("on-site", "onsite", "on site"))
    if policy is RemotePolicy.REMOTE and mentions_onsite and not mentions_remote:
        return True
    if policy is RemotePolicy.ONSITE and mentions_remote:
        return True
    return False


def _location_matches_preferred(location: str, preferred: list[str]) -> bool:
    location_tokens = set(_tokens(location))
    location_text = " ".join(_tokens(location))
    for item in preferred:
        preferred_tokens = set(_tokens(item))
        if not preferred_tokens:
            continue
        if preferred_tokens <= location_tokens:
            return True
        if " ".join(sorted(preferred_tokens)) in location_text:
            return True
        if _remote_us_compatible(preferred_tokens, location_tokens, location_text):
            return True
        significant = preferred_tokens - {"remote", "us", "usa", "united", "states"}
        if significant and significant <= location_tokens:
            return True
    return False


def _remote_us_compatible(preferred: set[str], location: set[str], location_text: str) -> bool:
    preferred_remote_us = bool(preferred & {"remote"}) and bool(
        preferred & {"us", "usa"} or {"united", "states"} <= preferred
    )
    location_us = bool(location & {"us", "usa"}) or "united states" in location_text
    location_remote = "remote" in location
    return preferred_remote_us and location_remote and location_us


def _role_family(title: str) -> str:
    tokens = set(_tokens(title))
    if tokens & _MANAGEMENT_TOKENS:
        return "management"
    if tokens & _DESIGN_TOKENS and not tokens & {"engineer", "engineering"}:
        return "design"
    if "scientist" in tokens and "engineer" not in tokens:
        return "science"
    if tokens & {"recruiter", "recruiting", "sourcer"}:
        return "recruiting"
    if tokens & _SOFTWARE_IC_TOKENS:
        return "software_ic"
    return "unknown"


def _specializations(title: str) -> set[str]:
    tokens = set(_tokens(title))
    return {name for name, markers in _SPECIALIZATIONS.items() if tokens & markers}


def _detect_industries(blob: str) -> set[str]:
    found: set[str] = set()
    for industry, aliases in _INDUSTRY_ALIASES.items():
        if any(alias in blob for alias in aliases):
            found.add(industry)
    return found


def _tokens(text: str) -> list[str]:
    normalized = (
        text.lower()
        .replace("full-stack", "fullstack")
        .replace("full stack", "fullstack")
        .replace("front-end", "frontend")
        .replace("front end", "frontend")
        .replace("back-end", "backend")
        .replace("back end", "backend")
        .replace("on-site", "onsite")
    )
    return _WORD.findall(normalized)


def _normalize_key(value: str) -> str:
    return " ".join(_tokens(value))


def _annual_amount(compensation: Compensation) -> int:
    if compensation.period == "hour":
        return compensation.amount * 2080
    if compensation.period == "month":
        return compensation.amount * 12
    return compensation.amount


def _compensation(value: dict[str, Any] | Compensation | None) -> Compensation | None:
    if value is None:
        return None
    if isinstance(value, Compensation):
        return value
    return Compensation.model_validate(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]
