"""Candidate profile and evidence HTTP API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import EvidenceCategory
from app.schemas.candidate import CandidateEvidenceListResponse, CandidateProfileRead
from app.services.candidate import (
    ProfileNotFoundError,
    evidence_to_read,
    list_evidence,
    profile_to_read,
    require_profile,
)

router = APIRouter(prefix="/candidate", tags=["candidate"])

_PROFILE_NOT_FOUND = "Candidate profile not found. Run: uv run python scripts/seed_candidate.py"


@router.get("/profile", response_model=CandidateProfileRead)
def get_candidate_profile(session: Annotated[Session, Depends(get_db)]) -> CandidateProfileRead:
    try:
        profile = require_profile(session)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_PROFILE_NOT_FOUND) from exc
    return profile_to_read(profile)


@router.get("/evidence", response_model=CandidateEvidenceListResponse)
def get_candidate_evidence(
    session: Annotated[Session, Depends(get_db)],
    category: Annotated[EvidenceCategory | None, Query()] = None,
) -> CandidateEvidenceListResponse:
    try:
        records = list_evidence(session, category=category)
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_PROFILE_NOT_FOUND) from exc
    return CandidateEvidenceListResponse(items=[evidence_to_read(item) for item in records])
