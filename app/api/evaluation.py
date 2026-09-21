"""Batch job evaluation HTTP API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.agents.job_evaluation import JobEvaluationRunner
from app.api.deps import get_db, get_evaluation_runner
from app.db import Database
from app.schemas.evaluation import BatchEvaluationRequest, BatchEvaluationResult
from app.services.batch_evaluation import run_batch_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/batch", response_model=BatchEvaluationResult, status_code=status.HTTP_200_OK)
def post_evaluation_batch(
    payload: BatchEvaluationRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    runner: Annotated[JobEvaluationRunner, Depends(get_evaluation_runner)],
) -> BatchEvaluationResult:
    database: Database = request.app.state.database
    return run_batch_evaluation(
        session,
        payload,
        runner=runner,
        session_factory=database.session_factory,
    )
