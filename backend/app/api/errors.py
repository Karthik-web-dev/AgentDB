"""Error signature API (novelty 8).

Both endpoints read through the owned views from migration 009, so the database returns
only the caller's signatures and runs, even if a query here forgot a filter.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.error import ErrorSignatureResponse
from app.schemas.run import RunResponse

router = APIRouter(prefix=f"{settings.API_V1_STR}/errors", tags=["Errors"])


@router.get("/signatures", response_model=List[ErrorSignatureResponse])
def list_error_signatures(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ErrorSignatureResponse]:
    """Distinct error messages, most frequent first. Digits are normalised, so near-identical errors group together."""
    rows = db.execute(
        text(
            "SELECT id, signature_hash, normalized_message, occurrences, first_seen, last_seen "
            "FROM v_owned_error_signatures "
            "ORDER BY occurrences DESC, last_seen DESC, id DESC "
            "LIMIT :limit OFFSET :skip"
        ),
        {"limit": limit, "skip": skip},
    ).mappings().all()
    return [ErrorSignatureResponse(**row) for row in rows]


@router.get("/signatures/{signature_id}/runs", response_model=List[RunResponse])
def list_runs_for_signature(
    signature_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[RunResponse]:
    """Runs whose error belongs to this signature, newest first."""
    owned = db.execute(
        text("SELECT id FROM v_owned_error_signatures WHERE id = :sid"),
        {"sid": signature_id},
    ).scalar_one_or_none()
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Error signature not found.")

    rows = db.execute(
        text(
            "SELECT id, agent_id, task_id, parent_run_id, error_signature_id, status, started_at, "
            "completed_at, execution_time_ms, error_message, created_at "
            "FROM v_owned_runs WHERE error_signature_id = :sid "
            "ORDER BY id DESC LIMIT :limit OFFSET :skip"
        ),
        {"sid": signature_id, "limit": limit, "skip": skip},
    ).mappings().all()
    return [RunResponse(**row) for row in rows]
