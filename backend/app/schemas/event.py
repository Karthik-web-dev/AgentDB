"""Event Management API schemas for AgentDB.

Pydantic v2 schemas for Event endpoints.
Follows the same patterns as Run schemas.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class EventCreate(BaseModel):
    """Payload accepted for POST /api/events.

    Only run_id, event_type, event_name, and payload are accepted.
    user_id is never accepted from the client; it is derived through
    the run → agent → user ownership chain.
    """

    run_id: int
    event_type: str
    event_name: str
    payload: Optional[dict] = None

    @field_validator("run_id")
    @classmethod
    def run_id_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("run_id must be a positive integer.")
        return v

    @field_validator("event_type")
    @classmethod
    def event_type_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("event_type must not be empty.")
        if len(v) > 50:
            raise ValueError("event_type must be at most 50 characters.")
        return v

    @field_validator("event_name")
    @classmethod
    def event_name_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("event_name must not be empty.")
        if len(v) > 100:
            raise ValueError("event_name must be at most 100 characters.")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EventResponse(BaseModel):
    """Safe public representation of an event."""

    id: int
    run_id: int
    event_type: str
    event_name: str
    payload: Optional[dict]
    timestamp: datetime

    model_config = {"from_attributes": True}


class EventListItem(BaseModel):
    """Minimal event representation for list endpoints."""

    id: int
    run_id: int
    event_type: str
    event_name: str
    timestamp: datetime

    model_config = {"from_attributes": True}