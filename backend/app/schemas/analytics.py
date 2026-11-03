"""Analytics response schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class LatencyAnomaly(BaseModel):
    run_id: int
    agent_id: int
    started_at: datetime
    latency_ms: int
    baseline_mean_ms: float
    baseline_stddev_ms: Optional[float]
    baseline_size: int
    z_score: Optional[float]
    detection_reason: str  # "z_score" or "flat_baseline"


class AgentCostRow(BaseModel):
    agent_id: int
    agent_name: str
    total_runs: int
    priced_runs: int
    unpriced_runs: int
    runs_without_usage: int
    input_tokens: float
    output_tokens: float
    total_cost_usd: float


class RunCostRow(BaseModel):
    run_id: int
    agent_id: int
    started_at: datetime
    input_tokens: float
    output_tokens: float
    cost_usd: Optional[float]
    attribution_method: str  # direct | unpriced | no_usage


class AgentOverviewRow(BaseModel):
    agent_id: int
    agent_name: str
    runs_total: int
    runs_completed: int
    runs_failed: int
    failure_rate_pct: float
    avg_latency_ms: Optional[float]
    max_latency_ms: Optional[int]
