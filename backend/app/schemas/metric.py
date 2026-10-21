"""Metric Management API schemas for AgentDB.

Pydantic v2 schemas for Metric endpoints.
Follows the same patterns as Log and Run schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MetricResponse(BaseModel):
    """Safe public representation of a metric.

    Only exposes metric data through the ownership boundary.
    user_id is never exposed directly; ownership is through
    User → Agent → Run → Metric chain.
    """

    id: int
    run_id: int
    metric_name: str
    metric_value: float
    unit: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class MetricListItem(BaseModel):
    """Minimal metric representation for list endpoints."""

    id: int
    run_id: int
    metric_name: str
    metric_value: float
    unit: str
    timestamp: datetime

    model_config = {"from_attributes": True}