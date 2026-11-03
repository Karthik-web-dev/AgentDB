from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.core.config import settings
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentListItem

router = APIRouter(prefix=f"{settings.API_V1_STR}/agents", tags=["Agents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_ownership(db: Session, agent_id: int, current_user: User) -> Agent:
    """Return agent if it belongs to current_user, else raise 404.

    Uses a single query to avoid disclosing agent existence to non-owners.
    """
    stmt = select(Agent).where(Agent.id == agent_id, Agent.user_id == current_user.id)
    result = db.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )
    return agent


# ---------------------------------------------------------------------------
# CREATE: POST /api/agents
# ---------------------------------------------------------------------------

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """Create a new agent owned by the authenticated user."""
    # NOTE: user_id is NOT accepted from the client; we inject it.
    db_agent = Agent(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        model=payload.model,
        environment=payload.environment,
        status=payload.status,
        version=payload.version,
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


# ---------------------------------------------------------------------------
# LIST: GET /api/agents
# ---------------------------------------------------------------------------

@router.get("", response_model=list[AgentListItem])
def list_agents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AgentListItem]:
    """Return only the authenticated user's agents with pagination."""
    stmt = select(Agent).where(Agent.user_id == current_user.id).offset(skip).limit(min(limit, 100))
    result = db.execute(stmt)
    agents = result.scalars().all()
    return agents


# ---------------------------------------------------------------------------
# GET SINGLE: GET /api/agents/{agent_id}
# ---------------------------------------------------------------------------

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """Return the agent if it belongs to the authenticated user."""
    agent = _check_ownership(db, agent_id, current_user)
    return agent


# ---------------------------------------------------------------------------
# UPDATE: PATCH /api/agents/{agent_id}
# ---------------------------------------------------------------------------

@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """Partial update of an agent owned by the authenticated user."""
    agent = _check_ownership(db, agent_id, current_user)

    # Apply only the fields that were provided (partial update)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    db.commit()
    db.refresh(agent)
    return agent


# ---------------------------------------------------------------------------
# DELETE: DELETE /api/agents/{agent_id}
# ---------------------------------------------------------------------------

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete an agent owned by the authenticated user.

    Respects database foreign-key restrictions. If deletion is blocked
    by dependent records (runs, logs, etc.), a 409 is returned with
    a clear message so the historical data is preserved.
    """
    agent = _check_ownership(db, agent_id, current_user)

    try:
        db.delete(agent)
        db.commit()
    except Exception as e:
        db.rollback()
        # Foreign-key violation or other DB error — preserve historical data
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete agent: dependent historical records exist. "
            "Remove associated runs, logs, events, or metrics first.",
        ) from e

    # 204 No Content — no response body
    return None