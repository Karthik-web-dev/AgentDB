"""Alert rule and firing schemas. Values mirror the alerts CHECK constraints in schema.sql and migrations."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_OPERATORS = {">", ">=", "<", "<=", "==", "!="}
ALLOWED_RULE_STATUSES = {"active", "disabled", "resolved"}  # 'triggered' is set by the engine only
FAILURE_METRIC_NAME = "run_failures"  # fixed label for failure-window rules


class AlertCreate(BaseModel):
    """Payload for POST /api/v1/alerts.

    threshold rule:       metric_name + condition_operator + threshold_value
                          e.g. latency_ms > 2000
    failure_window rule:  threshold_value = number of failed runs; time_window_minutes = window
                          e.g. "5 failures within 10 minutes". metric_name and operator are fixed.
    """

    rule_name: str = Field(min_length=1, max_length=100)
    rule_type: Literal["threshold", "failure_window"] = "threshold"
    metric_name: Optional[str] = Field(default=None, max_length=50)
    condition_operator: Optional[str] = None
    threshold_value: float
    time_window_minutes: int = Field(default=15, ge=1, le=10080)
    agent_id: Optional[int] = Field(default=None, gt=0, description="NULL applies the rule to all your agents")

    @field_validator("rule_name")
    @classmethod
    def rule_name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("condition_operator")
    @classmethod
    def operator_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_OPERATORS:
            raise ValueError(f"condition_operator must be one of {sorted(ALLOWED_OPERATORS)}")
        return v

    @model_validator(mode="after")
    def check_rule_shape(self):
        if self.rule_type == "threshold":
            if not self.metric_name or not self.metric_name.strip():
                raise ValueError("metric_name is required for threshold rules")
            if self.condition_operator is None:
                raise ValueError("condition_operator is required for threshold rules")
            self.metric_name = self.metric_name.strip()
        else:
            if self.threshold_value < 1 or self.threshold_value != int(self.threshold_value):
                raise ValueError("failure_window threshold_value must be a whole number of failures, at least 1")
            self.metric_name = FAILURE_METRIC_NAME
            self.condition_operator = ">="
        return self


class AlertUpdate(BaseModel):
    """Payload for PATCH /api/v1/alerts/{id}. Only provided fields change."""

    rule_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    condition_operator: Optional[str] = None
    threshold_value: Optional[float] = None
    time_window_minutes: Optional[int] = Field(default=None, ge=1, le=10080)
    status: Optional[str] = None

    @field_validator("condition_operator")
    @classmethod
    def operator_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_OPERATORS:
            raise ValueError(f"condition_operator must be one of {sorted(ALLOWED_OPERATORS)}")
        return v

    @field_validator("status")
    @classmethod
    def status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_RULE_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(ALLOWED_RULE_STATUSES)}; 'triggered' is set automatically"
            )
        return v


class AlertResponse(BaseModel):
    id: int
    user_id: int
    agent_id: Optional[int]
    rule_name: str
    rule_type: str
    metric_name: str
    condition_operator: str
    threshold_value: float
    time_window_minutes: int
    status: str
    last_triggered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertFiringResponse(BaseModel):
    id: int
    alert_id: int
    metric_id: Optional[int]
    run_id: Optional[int]
    observed_value: float
    threshold_value: float
    fired_at: datetime

    model_config = {"from_attributes": True}
