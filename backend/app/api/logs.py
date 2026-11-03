"""Log Management API routers for AgentDB.

Implements read-only Log endpoints with proper JWT authentication
and ownership enforcement through the chain: User → Agent → Run → Log.

Logs are read-only: no CREATE, PATCH, or DELETE endpoints.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_, func, cast, String as SQLString
from app.core.config import settings
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.run import Run
from app.models.log import Log
from app.schemas.log import LogResponse, LogListItem, LogList


router = APIRouter(prefix=f"{settings.API_V1_STR}/logs", tags=["Logs"])


# ---------------------------------------------------------------------------
# Helper: verify run ownership
# ---------------------------------------------------------------------------

def _check_run_ownership(db: Session, run_id: int, current_user: User) -> Run:
    """Return run if it belongs to an agent owned by current_user, else raise 404."""
    stmt = select(Run).join(Run.agent).where(Run.id == run_id, Agent.user_id == current_user.id)
    result = db.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found or not owned by user.",
        )
    return run


# ---------------------------------------------------------------------------
# Helper: verify log ownership
# ---------------------------------------------------------------------------

def _check_log_ownership(db: Session, log_id: int, current_user: User) -> Log:
    """Return log if it belongs to a run owned by current_user, else raise 404."""
    stmt = select(Log).where(Log.id == log_id)
    result = db.execute(stmt)
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log not found.",
        )
    # Verify the log's run belongs to user
    _check_run_ownership(db, log.run_id, current_user)  # raises 404 if not owned
    return log


# ---------------------------------------------------------------------------
# LIST: GET /api/logs
# ---------------------------------------------------------------------------

@router.get("", response_model=List[LogListItem])
def list_logs(
    skip: int = 0,
    limit: int = 100,
    severity: Optional[str] = None,
    agent_id: Optional[int] = None,
    run_id: Optional[int] = None,
    search: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[LogListItem]:
    """Return only the authenticated user's logs with pagination and filtering.

    Ownership chain: User → Agent → Run → Log
    All filtering respects the ownership boundary.
    """
    if skip < 0:
        raise HTTPException(
            status_code=422,
            detail="skip must be >= 0",
        )
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 100",
        )

    # Base query: logs joined with run + agent to enforce ownership
    stmt = select(Log).join(Log.run).join(Run.agent).where(Agent.user_id == current_user.id)

    # Severity filter
    if severity is not None:
        stmt = stmt.where(Log.severity == severity)

    # Agent filter (denormalized agent_id)
    if agent_id is not None:
        stmt = stmt.where(Log.agent_id == agent_id)

    # Run filter
    if run_id is not None:
        stmt = stmt.where(Log.run_id == run_id)

    # Free-text search on message
    if search is not None and search.strip():
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(Log.message.ilike(search_pattern))

    # Timestamp range filter
    if start_time is not None:
        stmt = stmt.where(Log.timestamp >= start_time)
    if end_time is not None:
        # end_time inclusive: go to next day start or just use >= comparison
        stmt = stmt.where(Log.timestamp <= end_time)

    # Order by newest first
    stmt = stmt.order_by(Log.timestamp.desc())

    # Pagination
    stmt = stmt.offset(skip).limit(min(limit, 100))

    result = db.execute(stmt)
    logs = result.scalars().all()
    return logs


# ---------------------------------------------------------------------------
# GET SINGLE: GET /api/logs/{log_id}
# ---------------------------------------------------------------------------

@router.get("/{log_id}", response_model=LogResponse)
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LogResponse:
    """Return a single log if it belongs to the authenticated user.

    404 if log does not exist or is not owned by the user.
    Never exposes another user's log.
    """
    log = _check_log_ownership(db, log_id, current_user)
    return log