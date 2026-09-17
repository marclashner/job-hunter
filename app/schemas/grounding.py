"""Provenance wrappers so agents can distinguish evidence, interpretation, and unknowns."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Provenance


class FieldGrounding(BaseModel):
    provenance: Provenance
    evidence_ids: list[UUID] = Field(default_factory=list)
    interpretation_notes: str | None = None


class GroundedValue[T](BaseModel):
    """A profile field as agents must consume it."""

    value: T | None = None
    provenance: Provenance
    evidence_ids: list[UUID] = Field(default_factory=list)
    interpretation_notes: str | None = None

    @model_validator(mode="after")
    def enforce_provenance_contract(self) -> GroundedValue[T]:
        if self.provenance is Provenance.UNKNOWN:
            if self.value is not None:
                raise ValueError("unknown fields must not carry a value")
            if self.evidence_ids:
                raise ValueError("unknown fields must not cite evidence")
            if self.interpretation_notes:
                raise ValueError("unknown fields must not include interpretation notes")
            return self
        if self.provenance is Provenance.EVIDENCE_BACKED:
            if self.value is None:
                raise ValueError("evidence_backed fields require a value")
            if not self.evidence_ids:
                raise ValueError("evidence_backed fields require at least one evidence id")
            return self
        if self.provenance is Provenance.DERIVED:
            if self.value is None:
                raise ValueError("derived fields require a value")
            if not self.interpretation_notes:
                raise ValueError("derived fields require interpretation_notes")
            if not self.evidence_ids:
                raise ValueError("derived fields must cite the evidence they interpret")
            return self
        raise ValueError(f"unsupported provenance: {self.provenance}")
