from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListItem

router = APIRouter(prefix=f"{settings.API_V1_STR}/tasks", tags=["Tasks"])


# ---------------------------------------------------------------------------
# Helper: verify agent ownership
# ---------------------------------------------------------------------------

def _check_agent_ownership(
    db: Session, agent_id: int, current_user: User
) -> Agent:
    """Return agent if it belongs to current_user, else raise 404.

    Uses a single query to avoid disclosing agent existence to non-owners.
    """
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
# Helper: verify task ownership
# ---------------------------------------------------------------------------

def _check_task_ownership(db: Session, task_id: int, current_user: User) -> Task:
    """Return task if it belongs to a agent owned by current_user, else raise 404.

    Uses a single join query to avoid disclosing task existence to non-owners.
    """
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
# CREATE: POST /api/tasks
# ---------------------------------------------------------------------------

@router.post(
    "", response_model=TaskResponse, status_code=status.HTTP_201_CREATED
)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """Create a new task for an agent owned by the authenticated user.

    - agent_id must reference an agent owned by the user.
    - user_id is never accepted from the client.
    """
    # Verify the agent belongs to the current user
    _check_agent_ownership(db, payload.agent_id, current_user)

    db_task = Task(
        agent_id=payload.agent_id,
        title=payload.title,
        description=payload.description,
        status=payload.status or "pending",
        priority=payload.priority or "medium",
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


# ---------------------------------------------------------------------------
# LIST: GET /api/tasks
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TaskListItem])
def list_tasks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaskListItem]:
    """Return only the authenticated user's tasks with pagination.

    Tasks belonging to agents owned by the user are returned.
    """
    stmt = (
        select(Task)
        .join(Task.agent)
        .where(Agent.user_id == current_user.id)
        .offset(skip)
        .limit(min(limit, 100))
    )
    result = db.execute(stmt)
    tasks = result.scalars().all()
    return tasks


# ---------------------------------------------------------------------------
# GET SINGLE: GET /api/tasks/{task_id}
# ---------------------------------------------------------------------------

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """Return the task if it belongs to an agent owned by the authenticated user."""
    task = _check_task_ownership(db, task_id, current_user)
    return task


# ---------------------------------------------------------------------------
# PATCH: PATCH /api/tasks/{task_id}
# ---------------------------------------------------------------------------

@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """Partial update of a task owned by the authenticated user.

    - Only provided fields are updated (partial update).
    - Ownership cannot be changed.
    - Task ID cannot be changed.
    """
    task = _check_task_ownership(db, task_id, current_user)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# DELETE: DELETE /api/tasks/{task_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{task_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a task owned by the authenticated user.

    Respects database foreign-key constraints (RESTRICT on agent_id).
    If deletion is blocked by dependent records (runs), a 409 is returned.
    """
    task = _check_task_ownership(db, task_id, current_user)

    try:
        db.delete(task)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete task: dependent records exist (e.g. runs). "
            "Remove associated runs first.",
        ) from e
    # 204 No Content — no response body
    return None