"""Candidate service tests without a live database."""

import uuid

from app.models.candidate import CandidateEvidence, CandidateProfile
from app.models.enums import EvidenceCategory, Provenance
from app.services.candidate import profile_to_read
from app.services.candidate_seed import load_seed_bundle


def _profile(**overrides: object) -> CandidateProfile:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "key": "primary",
        "name": "Should not leak",
        "target_titles": ["Invented Title"],
        "seniority": "senior",
        "years_experience": 99,
        "preferred_locations": [],
        "remote_preference": None,
        "minimum_compensation": None,
        "target_compensation": None,
        "employment_preferences": [],
        "industries": [],
        "preferred_company_stages": [],
        "technologies": ["InventedLang"],
        "domains": [],
        "ai_experience": "Invented foundational model research",
        "healthcare_experience": None,
        "leadership_experience": None,
        "summary": "Invented summary",
        "field_grounding": {},
        "evidence": [],
    }
    values.update(overrides)
    return CandidateProfile(**values)  # type: ignore[arg-type]


def test_missing_grounding_is_unknown_and_does_not_leak_stored_values() -> None:
    read = profile_to_read(_profile())
    assert read.ai_experience.provenance is Provenance.UNKNOWN
    assert read.ai_experience.value is None
    assert read.name.value is None
    assert "ai_experience" in read.unknown_fields
    assert EvidenceCategory.FRONTEND in read.unknown_categories


def test_evidence_backed_field_keeps_value_and_ids() -> None:
    evidence_id = uuid.uuid4()
    evidence = CandidateEvidence(
        id=evidence_id,
        profile_id=uuid.uuid4(),
        key="ai",
        category=EvidenceCategory.AI.value,
        claim="Shipped RAG",
        detailed_description="Details",
        technologies=["Python"],
        measurable_outcomes=["30% deflection"],
        source="resume",
        confidence="high",
        tags=[],
    )
    profile = _profile(
        ai_experience="Shipped production RAG with evaluation",
        field_grounding={
            "ai_experience": {
                "provenance": "evidence_backed",
                "evidence_ids": [str(evidence_id)],
                "interpretation_notes": None,
            }
        },
        evidence=[evidence],
    )
    read = profile_to_read(profile)
    assert read.ai_experience.provenance is Provenance.EVIDENCE_BACKED
    assert read.ai_experience.value == "Shipped production RAG with evaluation"
    assert read.ai_experience.evidence_ids == [evidence_id]
    assert EvidenceCategory.AI in (read.demonstrated_categories.value or [])
    assert EvidenceCategory.FRONTEND in read.unknown_categories


def test_seed_json_is_valid() -> None:
    bundle = load_seed_bundle()
    assert bundle.profile.key == "primary"
    assert bundle.evidence
    assert all(item.key for item in bundle.evidence)
    assert "frontend" not in {item.category.value for item in bundle.evidence}
