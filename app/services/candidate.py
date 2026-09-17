"""Candidate profile read/replace services.

Agents consume the read models produced here. Stored column values are suppressed
when provenance is unknown so ungrounded claims cannot leak into prompts.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.candidate import CandidateEvidence, CandidateProfile
from app.models.enums import (
    PROFILE_GROUNDABLE_FIELDS,
    ConfidenceLevel,
    EvidenceCategory,
    EvidenceSource,
    Provenance,
)
from app.schemas.candidate import (
    CandidateEvidenceRead,
    CandidateProfileRead,
    Compensation,
    SeedBundle,
)
from app.schemas.grounding import FieldGrounding, GroundedValue

PRIMARY_PROFILE_KEY = "primary"


class ProfileNotFoundError(LookupError):
    """Raised when the requested candidate profile is not in the database."""


def get_profile_by_key(session: Session, key: str = PRIMARY_PROFILE_KEY) -> CandidateProfile | None:
    statement = (
        select(CandidateProfile)
        .options(selectinload(CandidateProfile.evidence))
        .where(CandidateProfile.key == key)
    )
    return session.scalars(statement).one_or_none()


def require_profile(session: Session, key: str = PRIMARY_PROFILE_KEY) -> CandidateProfile:
    profile = get_profile_by_key(session, key)
    if profile is None:
        raise ProfileNotFoundError(key)
    return profile


def list_evidence(
    session: Session,
    *,
    key: str = PRIMARY_PROFILE_KEY,
    category: EvidenceCategory | None = None,
) -> list[CandidateEvidence]:
    profile = require_profile(session, key)
    records = list(profile.evidence)
    if category is not None:
        records = [item for item in records if item.category == category.value]
    return records


def evidence_to_read(record: CandidateEvidence) -> CandidateEvidenceRead:
    return CandidateEvidenceRead(
        id=record.id,
        key=record.key,
        category=EvidenceCategory(record.category),
        claim=record.claim,
        detailed_description=record.detailed_description,
        technologies=list(record.technologies),
        measurable_outcomes=list(record.measurable_outcomes),
        source=EvidenceSource(record.source),
        confidence=ConfidenceLevel(record.confidence),
        tags=list(record.tags),
    )


def profile_to_read(profile: CandidateProfile) -> CandidateProfileRead:
    evidence = list(profile.evidence)
    grounding = _load_grounding(profile.field_grounding)
    stored: dict[str, Any] = {
        "name": profile.name,
        "target_titles": profile.target_titles,
        "seniority": profile.seniority,
        "years_experience": profile.years_experience,
        "preferred_locations": profile.preferred_locations,
        "remote_preference": profile.remote_preference,
        "minimum_compensation": profile.minimum_compensation,
        "target_compensation": profile.target_compensation,
        "employment_preferences": profile.employment_preferences,
        "industries": profile.industries,
        "preferred_company_stages": profile.preferred_company_stages,
        "technologies": profile.technologies,
        "domains": profile.domains,
        "ai_experience": profile.ai_experience,
        "healthcare_experience": profile.healthcare_experience,
        "leadership_experience": profile.leadership_experience,
        "summary": profile.summary,
    }

    fields: dict[str, GroundedValue[Any]] = {}
    unknown_fields: list[str] = []
    for name in PROFILE_GROUNDABLE_FIELDS:
        wrapped = _ground_field(name, stored.get(name), grounding.get(name))
        fields[name] = wrapped
        if wrapped.provenance is Provenance.UNKNOWN:
            unknown_fields.append(name)

    demonstrated = _demonstrated_categories(evidence)
    known_categories = {item.category for item in evidence}
    unknown_categories: list[EvidenceCategory] = []
    for category in EvidenceCategory:
        if category is EvidenceCategory.SELF_REPORTED:
            continue
        if category.value not in known_categories:
            unknown_categories.append(category)

    return CandidateProfileRead(
        id=profile.id,
        key=profile.key,
        name=fields["name"],
        target_titles=fields["target_titles"],
        seniority=fields["seniority"],
        years_experience=fields["years_experience"],
        preferred_locations=fields["preferred_locations"],
        remote_preference=fields["remote_preference"],
        minimum_compensation=fields["minimum_compensation"],
        target_compensation=fields["target_compensation"],
        employment_preferences=fields["employment_preferences"],
        industries=fields["industries"],
        preferred_company_stages=fields["preferred_company_stages"],
        technologies=fields["technologies"],
        domains=fields["domains"],
        ai_experience=fields["ai_experience"],
        healthcare_experience=fields["healthcare_experience"],
        leadership_experience=fields["leadership_experience"],
        summary=fields["summary"],
        unknown_fields=unknown_fields,
        demonstrated_categories=demonstrated,
        unknown_categories=unknown_categories,
    )


def replace_from_seed(session: Session, bundle: SeedBundle) -> CandidateProfile:
    existing = get_profile_by_key(session, bundle.profile.key)
    if existing is not None:
        session.delete(existing)
        session.flush()

    profile_id = uuid.uuid4()
    evidence_records: list[CandidateEvidence] = []
    id_by_key: dict[str, uuid.UUID] = {}
    for item in bundle.evidence:
        evidence_id = uuid.uuid4()
        id_by_key[item.key] = evidence_id
        evidence_records.append(
            CandidateEvidence(
                id=evidence_id,
                profile_id=profile_id,
                key=item.key,
                category=item.category.value,
                claim=item.claim,
                detailed_description=item.detailed_description,
                technologies=item.technologies,
                measurable_outcomes=item.measurable_outcomes,
                source=item.source.value,
                confidence=item.confidence.value,
                tags=item.tags,
            )
        )

    missing_keys = _missing_evidence_keys(bundle, id_by_key)
    if missing_keys:
        raise ValueError(f"field_grounding cites unknown evidence keys: {sorted(missing_keys)}")

    profile = CandidateProfile(
        id=profile_id,
        key=bundle.profile.key,
        name=bundle.profile.name,
        target_titles=bundle.profile.target_titles,
        seniority=bundle.profile.seniority.value if bundle.profile.seniority else None,
        years_experience=bundle.profile.years_experience,
        preferred_locations=bundle.profile.preferred_locations,
        remote_preference=(
            bundle.profile.remote_preference.value if bundle.profile.remote_preference else None
        ),
        minimum_compensation=_dump_optional(bundle.profile.minimum_compensation),
        target_compensation=_dump_optional(bundle.profile.target_compensation),
        employment_preferences=[item.value for item in bundle.profile.employment_preferences],
        industries=bundle.profile.industries,
        preferred_company_stages=[item.value for item in bundle.profile.preferred_company_stages],
        technologies=bundle.profile.technologies,
        domains=bundle.profile.domains,
        ai_experience=bundle.profile.ai_experience,
        healthcare_experience=bundle.profile.healthcare_experience,
        leadership_experience=bundle.profile.leadership_experience,
        summary=bundle.profile.summary,
        field_grounding=_materialize_grounding(bundle, id_by_key),
        evidence=evidence_records,
    )
    # Validate the agent-facing contract before commit so bad seed data cannot land.
    profile_to_read(profile)
    session.add(profile)
    session.flush()
    return profile


def _dump_optional(model: Compensation | None) -> dict[str, Any] | None:
    if model is None:
        return None
    return model.model_dump()


def _missing_evidence_keys(bundle: SeedBundle, id_by_key: dict[str, uuid.UUID]) -> set[str]:
    cited: set[str] = set()
    for meta in bundle.profile.field_grounding.values():
        cited.update(meta.evidence_keys)
    return cited - set(id_by_key)


def _materialize_grounding(bundle: SeedBundle, id_by_key: dict[str, uuid.UUID]) -> dict[str, Any]:
    materialized: dict[str, Any] = {}
    for field, meta in bundle.profile.field_grounding.items():
        materialized[field] = {
            "provenance": meta.provenance.value,
            "evidence_ids": [str(id_by_key[key]) for key in meta.evidence_keys],
            "interpretation_notes": meta.interpretation_notes,
        }
    return materialized


def _load_grounding(raw: dict[str, Any]) -> dict[str, FieldGrounding]:
    loaded: dict[str, FieldGrounding] = {}
    for field, payload in raw.items():
        loaded[field] = FieldGrounding.model_validate(payload)
    return loaded


def _ground_field(name: str, stored: Any, meta: FieldGrounding | None) -> GroundedValue[Any]:
    if meta is None or meta.provenance is Provenance.UNKNOWN:
        return GroundedValue(value=None, provenance=Provenance.UNKNOWN)

    value = stored
    if name in {"minimum_compensation", "target_compensation"} and stored is not None:
        value = Compensation.model_validate(stored)
    if value in ([], {}):
        return GroundedValue(value=None, provenance=Provenance.UNKNOWN)
    return GroundedValue(
        value=value,
        provenance=meta.provenance,
        evidence_ids=list(meta.evidence_ids),
        interpretation_notes=meta.interpretation_notes,
    )


def _demonstrated_categories(
    evidence: list[CandidateEvidence],
) -> GroundedValue[list[EvidenceCategory]]:
    categories: list[EvidenceCategory] = []
    seen: set[str] = set()
    cited_ids: list[uuid.UUID] = []
    for item in evidence:
        if item.category == EvidenceCategory.SELF_REPORTED.value:
            continue
        if item.category in seen:
            continue
        seen.add(item.category)
        categories.append(EvidenceCategory(item.category))
        cited_ids.append(item.id)
    if not categories:
        return GroundedValue(value=None, provenance=Provenance.UNKNOWN)
    return GroundedValue(
        value=categories,
        provenance=Provenance.DERIVED,
        evidence_ids=cited_ids,
        interpretation_notes=(
            "Categories present on stored CandidateEvidence rows. "
            "Absence of a category means unknown, not a claim that the candidate lacks the skill."
        ),
    )
