"""Job board source sync endpoints."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import JobSource
from app.schemas.sources import SourceSyncResult
from app.services.source_sync import sync_jobs
from app.sources.base import JobBoardNotFoundError, JobSourceAdapter, JobSourceFetchError
from app.sources.greenhouse import GreenhouseClient
from app.sources.lever import LeverClient

router = APIRouter(prefix="/sources", tags=["sources"])

_SITE_SLUG = Path(
    min_length=1,
    max_length=128,
    pattern=r"^[A-Za-z0-9_-]+$",
    description="Public job-board slug",
)


def get_greenhouse_client() -> Iterator[GreenhouseClient]:
    client = GreenhouseClient()
    try:
        yield client
    finally:
        client.close()


def get_lever_client() -> Iterator[LeverClient]:
    client = LeverClient()
    try:
        yield client
    finally:
        client.close()


def _sync(
    session: Session,
    adapter: JobSourceAdapter,
    company_identifier: str,
    source: JobSource,
) -> SourceSyncResult:
    try:
        return sync_jobs(session, adapter, company_identifier, source=source)
    except JobBoardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobSourceFetchError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/greenhouse/{board_token}/sync",
    response_model=SourceSyncResult,
    summary="Sync Greenhouse board",
)
def sync_greenhouse_board(
    board_token: Annotated[str, _SITE_SLUG],
    session: Annotated[Session, Depends(get_db)],
    client: Annotated[GreenhouseClient, Depends(get_greenhouse_client)],
) -> SourceSyncResult:
    """Fetch `boards-api.greenhouse.io` jobs for a public board token and upsert."""
    return _sync(session, client, board_token, JobSource.GREENHOUSE)


@router.post("/lever/{site}/sync", response_model=SourceSyncResult, summary="Sync Lever site")
def sync_lever_site(
    site: Annotated[str, _SITE_SLUG],
    session: Annotated[Session, Depends(get_db)],
    client: Annotated[LeverClient, Depends(get_lever_client)],
) -> SourceSyncResult:
    """Fetch `api.lever.co` postings for a public site slug and upsert."""
    return _sync(session, client, site, JobSource.LEVER)
