from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from sqlalchemy import select, and_, or_, text

from app.core.config import settings
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.task import Task
from app.models.run import Run
from app.schemas.run import RunCreate, RunUpdate, RunResponse, RunListItem, SubtreeCost, TraceNode

router = APIRouter(prefix=f"{settings.API_V1_STR}/runs", tags=["Runs"])

# Statuses after which a run is finished and completed_at must be set.
TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


# ---------------------------------------------------------------------------
# Helper: verify agent ownership
# ---------------------------------------------------------------------------

def _check_agent_ownership(db: Session, agent_id: int, current_user: User) -> Agent:
    """Return agent if it belongs to current_user, else raise 404."""
    stmt = select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    result = db.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or not owned by user.",
        )
    return agent


# ---------------------------------------------------------------------------
# Helper: verify task ownership (task must belong to user's agent)
# ---------------------------------------------------------------------------

def _check_task_ownership(db: Session, task_id: int, current_user: User) -> Task:
    """Return task if it belongs to an agent owned by current_user, else raise 404."""
    stmt = select(Task).join(Task.agent).where(Task.id == task_id, Agent.user_id == current_user.id)
    result = db.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or not owned by user.",
        )
    return task


# ---------------------------------------------------------------------------
# Helper: verify run ownership
# ---------------------------------------------------------------------------

def _check_run_ownership(db: Session, run_id: int, current_user: User) -> Run:
    """Return run if it belongs to a agent owned by current_user, else raise 404."""
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
# CREATE: POST /api/runs
# ---------------------------------------------------------------------------

@router.post(
    "", response_model=RunResponse, status_code=status.HTTP_201_CREATED
)
def create_run(
    payload: RunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunResponse:
    """Create a new run for an agent owned by the authenticated user.

    - agent_id must reference an agent owned by the user.
    - task_id, if provided, must reference a task belonging to the same agent.
    - user_id is never accepted from the client; we inject it via the agent.
    - The composite FK (task_id, agent_id) is enforced at the database level.
    """
    # Verify the agent belongs to the current user
    agent = _check_agent_ownership(db, payload.agent_id, current_user)

    # If task_id is provided, verify it belongs to the same agent
    if payload.task_id is not None:
        # Verify task exists and belongs to this agent
        stmt = select(Task).where(Task.id == payload.task_id, Task.agent_id == payload.agent_id)
        result = db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task not found or does not belong to the specified agent.",
            )

    # A parent run must be one of the caller's runs (the database enforces the same rule).
    if payload.parent_run_id is not None:
        _check_run_ownership(db, payload.parent_run_id, current_user)

    # Create the run — user_id is derived from the agent, not accepted from client
    db_run = Run(
        agent_id=payload.agent_id,
        task_id=payload.task_id,
        parent_run_id=payload.parent_run_id,
        status=payload.status or "running",
        execution_time_ms=payload.execution_time_ms,
        error_message=payload.error_message,
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run


# ---------------------------------------------------------------------------
# LIST: GET /api/runs
# ---------------------------------------------------------------------------

@router.get(
    "", response_model=list[RunListItem]
)
def list_runs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RunListItem]:
    """Return only the authenticated user's runs with pagination.

    Runs belonging to agents owned by the user are returned.
    """
    # Query runs joined with agent to filter by user ownership
    stmt = (
        select(Run)
        .join(Run.agent)
        .where(Agent.user_id == current_user.id)
        .offset(skip)
        .limit(min(limit, 100))
    )
    result = db.execute(stmt)
    runs = result.scalars().all()
    return runs


# ---------------------------------------------------------------------------
# GET SINGLE: GET /api/runs/{run_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{run_id}", response_model=RunResponse
)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunResponse:
    """Return the run if it belongs to an agent owned by the authenticated user."""
    run = _check_run_ownership(db, run_id, current_user)
    return run


# ---------------------------------------------------------------------------
# PATCH: PATCH /api/runs/{run_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/{run_id}", response_model=RunResponse
)
def update_run(
    run_id: int,
    payload: RunUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RunResponse:
    """Partial update of a run owned by the authenticated user.

    Only status, execution_time_ms, and error_message can be updated.
    agent_id and task_id cannot be changed after creation.
    """
    run = _check_run_ownership(db, run_id, current_user)

    # Apply only the fields that were provided (partial update)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(run, key, value)

    # A run that reaches a terminal state gets its completion time recorded once.
    if run.status in TERMINAL_RUN_STATUSES and run.completed_at is None:
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(run)
    return run

# ---------------------------------------------------------------------------
# TRACE: GET /api/v1/runs/{run_id}/trace  (novelty 7)
# ---------------------------------------------------------------------------

@router.get("/{run_id}/trace", response_model=List[TraceNode])
def get_run_trace(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TraceNode]:
    """The run and every run it started (directly or indirectly), depth-first.

    The recursive walk runs inside sp_run_trace, which checks ownership in its anchor row.
    """
    _check_run_ownership(db, run_id, current_user)
    rows = db.execute(
        text("CALL sp_run_trace(:user_id, :run_id)"),
        {"user_id": current_user.id, "run_id": run_id},
    ).mappings().all()
    return [TraceNode(**row) for row in rows]


# ---------------------------------------------------------------------------
# SUBTREE COST: GET /api/v1/runs/{run_id}/subtree-cost  (novelty 7 + 6)
# ---------------------------------------------------------------------------

@router.get("/{run_id}/subtree-cost", response_model=SubtreeCost)
def get_run_subtree_cost(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SubtreeCost:
    """Total cost of a run and all of its descendants (attribution method: rollup)."""
    _check_run_ownership(db, run_id, current_user)
    row = db.execute(
        text("CALL sp_run_subtree_cost(:user_id, :run_id)"),
        {"user_id": current_user.id, "run_id": run_id},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found or not owned by user.")
    return SubtreeCost(**row)
