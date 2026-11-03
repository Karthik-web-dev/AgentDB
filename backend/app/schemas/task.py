from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    """Payload accepted for POST /api/tasks.

    Only agent_id, title, description, status, and priority are accepted.
    user_id is never accepted from the client; it is derived through
    task -> agent -> user ownership.
    """

    agent_id: int
    title: str

    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None

    @field_validator("agent_id")
    @classmethod
    def agent_id_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("agent_id must be a positive integer.")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty.")
        return v

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        valid = {"pending", "in_progress", "completed", "failed", "cancelled"}
        if v not in valid:
            raise ValueError(f"status must be one of {valid}.")
        return v

    @field_validator("priority")
    @classmethod
    def priority_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        valid = {"low", "medium", "high", "critical"}
        if v not in valid:
            raise ValueError(f"priority must be one of {valid}.")
        return v


class TaskUpdate(BaseModel):
    """Payload accepted for PATCH /api/tasks/{task_id} — partial update."""

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        valid = {"pending", "in_progress", "completed", "failed", "cancelled"}
        if v not in valid:
            raise ValueError(f"status must be one of {valid}.")
        return v

    @field_validator("priority")
    @classmethod
    def priority_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        valid = {"low", "medium", "high", "critical"}
        if v not in valid:
            raise ValueError(f"priority must be one of {valid}.")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TaskResponse(BaseModel):
    """Safe public representation of a task.

    Never exposes internal ownership logic; user_id is included on the
    agent but the frontend should treat it as owner-only.
    """

    id: int
    agent_id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListItem(BaseModel):
    """Minimal task representation for list endpoints."""

    id: int
    agent_id: int
    title: str
    status: str
    priority: str
    created_at: datetime

    model_config = {"from_attributes": True}