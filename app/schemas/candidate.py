"""Pydantic v2 schemas for candidate profile and evidence."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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
from app.schemas.grounding import GroundedValue

AGENT_USAGE_RULE = (
    "Never invent candidate experience. Use evidence_backed values as facts, "
    "treat derived values as interpretations that must stay faithful to cited evidence, "
    "and treat unknown values as missing information."
)


class Compensation(BaseModel):
    amount: int = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    period: str = Field(default="year")

    @field_validator("period")
    @classmethod
    def period_must_be_known(cls, value: str) -> str:
        allowed = {"year", "month", "hour"}
        if value not in allowed:
            raise ValueError(f"period must be one of {sorted(allowed)}")
        return value

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.upper()


class CandidateEvidenceRead(BaseModel):
    id: UUID
    key: str
    category: EvidenceCategory
    claim: str
    detailed_description: str
    technologies: list[str]
    measurable_outcomes: list[str]
    source: EvidenceSource
    confidence: ConfidenceLevel
    tags: list[str]


class CandidateEvidenceListResponse(BaseModel):
    items: list[CandidateEvidenceRead]
    agent_usage_rule: str = AGENT_USAGE_RULE


class CandidateProfileRead(BaseModel):
    id: UUID
    key: str
    name: GroundedValue[str]
    target_titles: GroundedValue[list[str]]
    seniority: GroundedValue[Seniority]
    years_experience: GroundedValue[float]
    preferred_locations: GroundedValue[list[str]]
    remote_preference: GroundedValue[RemotePreference]
    minimum_compensation: GroundedValue[Compensation]
    target_compensation: GroundedValue[Compensation]
    employment_preferences: GroundedValue[list[EmploymentType]]
    industries: GroundedValue[list[str]]
    preferred_company_stages: GroundedValue[list[CompanyStage]]
    technologies: GroundedValue[list[str]]
    domains: GroundedValue[list[str]]
    ai_experience: GroundedValue[str]
    healthcare_experience: GroundedValue[str]
    leadership_experience: GroundedValue[str]
    summary: GroundedValue[str]
    unknown_fields: list[str]
    demonstrated_categories: GroundedValue[list[EvidenceCategory]]
    unknown_categories: list[EvidenceCategory]
    agent_usage_rule: str = AGENT_USAGE_RULE


class SeedFieldGrounding(BaseModel):
    provenance: Provenance
    evidence_keys: list[str] = Field(default_factory=list)
    interpretation_notes: str | None = None


class SeedCompensation(Compensation):
    pass


class SeedCandidateProfile(BaseModel):
    key: str = "primary"
    name: str | None = None
    target_titles: list[str] = Field(default_factory=list)
    seniority: Seniority | None = None
    years_experience: float | None = None
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: RemotePreference | None = None
    minimum_compensation: SeedCompensation | None = None
    target_compensation: SeedCompensation | None = None
    employment_preferences: list[EmploymentType] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    preferred_company_stages: list[CompanyStage] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    ai_experience: str | None = None
    healthcare_experience: str | None = None
    leadership_experience: str | None = None
    summary: str | None = None
    field_grounding: dict[str, SeedFieldGrounding]

    @field_validator("field_grounding")
    @classmethod
    def grounding_keys_must_be_known(
        cls, value: dict[str, SeedFieldGrounding]
    ) -> dict[str, SeedFieldGrounding]:
        unknown = sorted(set(value) - set(PROFILE_GROUNDABLE_FIELDS))
        if unknown:
            raise ValueError(f"unknown grounding fields: {unknown}")
        return value


class SeedCandidateEvidence(BaseModel):
    key: str
    category: EvidenceCategory
    claim: str
    detailed_description: str
    technologies: list[str] = Field(default_factory=list)
    measurable_outcomes: list[str] = Field(default_factory=list)
    source: EvidenceSource
    confidence: ConfidenceLevel
    tags: list[str] = Field(default_factory=list)


class SeedBundle(BaseModel):
    profile: SeedCandidateProfile
    evidence: list[SeedCandidateEvidence]
