from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AgentCreate(BaseModel):
    """Payload accepted for POST /api/agents."""

    name: str
    description: Optional[str] = None
    model: str
    environment: str = "production"
    status: str = "active"
    version: str = "1.0.0"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty.")
        return v

    @field_validator("model")
    @classmethod
    def model_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("model must not be empty.")
        return v

    @field_validator("environment")
    @classmethod
    def environment_valid(cls, v: str) -> str:
        valid = {"production", "staging", "development"}
        v = v.strip().lower()
        if v not in valid:
            raise ValueError(f"environment must be one of {valid}.")
        return v

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        valid = {"active", "inactive", "maintenance"}
        v = v.strip().lower()
        if v not in valid:
            raise ValueError(f"status must be one of {valid}.")
        return v


class AgentUpdate(BaseModel):
    """Payload accepted for PATCH /api/agents/{agent_id} — partial update."""

    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    environment: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None

    @field_validator("environment")
    @classmethod
    def environment_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        valid = {"production", "staging", "development"}
        if v not in valid:
            raise ValueError(f"environment must be one of {valid}.")
        return v

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().lower()
        valid = {"active", "inactive", "maintenance"}
        if v not in valid:
            raise ValueError(f"status must be one of {valid}.")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AgentResponse(BaseModel):
    """Safe public representation of an agent.

    Never exposes internal ownership logic; user_id is included for
    completeness but the frontend should treat it as owner-only.
    """

    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    model: str
    environment: str
    status: str
    version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListItem(BaseModel):
    """Minimal agent representation for list endpoints."""

    id: int
    name: str
    model: str
    environment: str
    status: str
    version: str

    model_config = {"from_attributes": True}