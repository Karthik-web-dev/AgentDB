"""Log Management API schemas for AgentDB.

Pydantic v2 schemas for Log endpoints.
Follows the same patterns as Event and Run schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import AliasChoices, BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------


class LogResponse(BaseModel):
    """Safe public representation of a log.

    The ORM attribute is `metadata_` because `metadata` is reserved by
    SQLAlchemy's declarative base; the API still exposes it as `metadata`.
    """

    id: int
    run_id: int
    agent_id: int
    severity: str
    message: str
    log_metadata: Optional[dict] = Field(
        default=None,
        validation_alias=AliasChoices("metadata_", "metadata"),
        serialization_alias="metadata",
    )
    timestamp: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class LogListItem(BaseModel):
    """Minimal log representation for list endpoints."""

    id: int
    run_id: int
    agent_id: int
    severity: str
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Query/filters schemas
# ---------------------------------------------------------------------------


class LogList(BaseModel):
    """Query parameters for GET /api/logs."""

    skip: int = 0
    limit: int = 100
    severity: Optional[str] = None
    agent_id: Optional[int] = None
    run_id: Optional[int] = None
    search: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @field_validator("skip")
    @classmethod
    def skip_must_be_nonnegative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("skip must be >= 0")
        return v

    @field_validator("limit")
    @classmethod
    def limit_must_be_reasonable(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("limit must be between 1 and 100")
        return v