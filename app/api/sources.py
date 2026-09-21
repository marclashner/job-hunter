"""Job board source sync endpoints."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import JobSource
from app.schemas.sources import SourceSyncResult
from app.services.source_sync import sync_jobs
from app.sources.base import JobBoardNotFoundError, JobSourceFetchError
from app.sources.greenhouse import GreenhouseClient

router = APIRouter(prefix="/sources", tags=["sources"])

_BOARD_TOKEN = Path(
    min_length=1,
    max_length=128,
    pattern=r"^[A-Za-z0-9_-]+$",
    description="Greenhouse job-board token, e.g. the slug in boards.greenhouse.io/{token}",
)


def get_greenhouse_client() -> Iterator[GreenhouseClient]:
    client = GreenhouseClient()
    try:
        yield client
    finally:
        client.close()


@router.post("/greenhouse/{board_token}/sync", response_model=SourceSyncResult)
def sync_greenhouse_board(
    board_token: Annotated[str, _BOARD_TOKEN],
    session: Annotated[Session, Depends(get_db)],
    client: Annotated[GreenhouseClient, Depends(get_greenhouse_client)],
) -> SourceSyncResult:
    try:
        return sync_jobs(session, client, board_token, source=JobSource.GREENHOUSE)
    except JobBoardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobSourceFetchError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
