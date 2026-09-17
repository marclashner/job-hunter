"""Provenance contract tests."""

import pytest
from pydantic import ValidationError

from app.models.enums import Provenance
from app.schemas.grounding import GroundedValue


def test_unknown_forbids_values() -> None:
    with pytest.raises(ValidationError):
        GroundedValue[str](value="secret", provenance=Provenance.UNKNOWN)


def test_evidence_backed_requires_ids() -> None:
    with pytest.raises(ValidationError):
        GroundedValue[str](value="claim", provenance=Provenance.EVIDENCE_BACKED, evidence_ids=[])


def test_derived_requires_notes_and_ids() -> None:
    with pytest.raises(ValidationError):
        GroundedValue[str](
            value="summary",
            provenance=Provenance.DERIVED,
            evidence_ids=[],
            interpretation_notes="from evidence",
        )
    with pytest.raises(ValidationError):
        GroundedValue[str](
            value="summary",
            provenance=Provenance.DERIVED,
            evidence_ids=["00000000-0000-0000-0000-000000000001"],
            interpretation_notes=None,
        )
