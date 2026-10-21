"""Metric Management API routers for AgentDB.

Implements Metric endpoints with proper JWT authentication
and ownership enforcement through the chain:
User → Agent → Run → Metric.

Metrics are read-only: no CREATE, PATCH, or DELETE endpoints.
Only GET/list and GET/{id} endpoints are provided.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_, func

from app.core.config import settings
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.run import Run
from app.models.metric import Metric
from app.schemas.metric import MetricResponse, MetricListItem

router = APIRouter(prefix=f"{settings.API_V1_STR}/metrics", tags=["Metrics"])


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
# Helper: verify metric ownership
# ---------------------------------------------------------------------------

def _check_metric_ownership(db: Session, metric_id: int, current_user: User) -> Metric:
    """Return metric if it belongs to a run owned by current_user, else raise 404."""
    stmt = select(Metric).where(Metric.id == metric_id)
    result = db.execute(stmt)
    metric = result.scalar_one_or_none()
    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found.",
        )
    # Verify the metric's run belongs to user
    _check_run_ownership(db, metric.run_id, current_user)  # raises 404 if not owned
    return metric


# ---------------------------------------------------------------------------
# LIST: GET /api/metrics
# ---------------------------------------------------------------------------

@router.get("", response_model=List[MetricListItem])
def list_metrics(
    skip: int = 0,
    limit: int = 100,
    metric_name: Optional[str] = None,
    run_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[MetricListItem]:
    """Return only the authenticated user's metrics with pagination and filtering.

    Ownership chain: User → Agent → Run → Metric
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

    # Base query: metrics joined with run + agent to enforce ownership
    stmt = select(Metric).join(Metric.run).join(Run.agent).where(Agent.user_id == current_user.id)

    # Metric name filter
    if metric_name is not None:
        stmt = stmt.where(Metric.metric_name == metric_name)

    # Run filter
    if run_id is not None:
        stmt = stmt.where(Metric.run_id == run_id)

    # Order by newest first
    stmt = stmt.order_by(Metric.timestamp.desc())

    # Pagination
    stmt = stmt.offset(skip).limit(min(limit, 100))

    result = db.execute(stmt)
    metrics = result.scalars().all()
    return metrics


# ---------------------------------------------------------------------------
# GET SINGLE: GET /api/metrics/{metric_id}
# ---------------------------------------------------------------------------

@router.get("/{metric_id}", response_model=MetricResponse)
def get_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MetricResponse:
    """Return a single metric if it belongs to the authenticated user.

    404 if metric does not exist or is not owned by the user.
    Never exposes another user's metric.
    """
    metric = _check_metric_ownership(db, metric_id, current_user)
    return metric