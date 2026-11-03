"""Analytics API. Heavy lifting happens in MySQL (views and stored procedures)."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.agent import Agent
from app.models.user import User
from app.schemas.analytics import AgentCostRow, AgentOverviewRow, LatencyAnomaly, RunCostRow

router = APIRouter(prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics"])

# Earliest value accepted by MySQL DATETIME, used when no lower bound is given.
_EPOCH = datetime(1970, 1, 1)


def _as_naive_utc(value: datetime) -> datetime:
    """MySQL DATETIME is naive; convert timezone-aware input to naive UTC."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


@router.get("/latency-anomalies", response_model=List[LatencyAnomaly])
def latency_anomalies(
    agent_id: Optional[int] = None,
    z_threshold: float = Query(default=3.0, gt=0, le=100),
    since: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[LatencyAnomaly]:
    """Completed runs whose latency deviates from the agent's recent baseline.

    The baseline is the previous 20 completed runs of the same agent (see
    database/migrations/003_latency_anomaly.sql). Ownership is enforced inside
    sp_detect_latency_anomalies, so only your own agents can appear in the result.
    """
    if agent_id is not None:
        owned = db.execute(
            select(Agent.id).where(Agent.id == agent_id, Agent.user_id == current_user.id)
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found or not owned by user.")

    since_value = _as_naive_utc(since) if since is not None else _EPOCH
    rows = db.execute(
        text("CALL sp_detect_latency_anomalies(:user_id, :agent_id, :z_threshold, :since)"),
        {
            "user_id": current_user.id,
            "agent_id": agent_id,
            "z_threshold": z_threshold,
            "since": since_value,
        },
    ).mappings().all()
    return [LatencyAnomaly(**row) for row in rows]


# Latest value accepted by MySQL DATETIME, used when no upper bound is given.
_FAR_FUTURE = datetime(9999, 12, 31, 23, 59, 59)


@router.get("/cost", response_model=List[AgentCostRow])
def cost_by_agent(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AgentCostRow]:
    """Token usage and cost per agent for a time range. Costs come from model_pricing (see migration 006)."""
    rows = db.execute(
        text("CALL sp_agent_cost_report(:user_id, :since, :until)"),
        {
            "user_id": current_user.id,
            "since": _as_naive_utc(since) if since else _EPOCH,
            "until": _as_naive_utc(until) if until else _FAR_FUTURE,
        },
    ).mappings().all()
    return [AgentCostRow(**row) for row in rows]


@router.get("/runs-cost", response_model=List[RunCostRow])
def cost_by_run(
    agent_id: Optional[int] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[RunCostRow]:
    """Per-run cost with the attribution method that produced each number."""
    if agent_id is not None:
        owned = db.execute(
            select(Agent.id).where(Agent.id == agent_id, Agent.user_id == current_user.id)
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found or not owned by user.")
    rows = db.execute(
        text("CALL sp_run_cost_breakdown(:user_id, :agent_id, :since, :until)"),
        {
            "user_id": current_user.id,
            "agent_id": agent_id,
            "since": _as_naive_utc(since) if since else _EPOCH,
            "until": _as_naive_utc(until) if until else _FAR_FUTURE,
        },
    ).mappings().all()
    return [RunCostRow(**row) for row in rows]


@router.get("/overview", response_model=List[AgentOverviewRow])
def overview(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AgentOverviewRow]:
    """Per-agent run totals, failure rate and latency for a range, read from the hourly rollups.

    The requested range is refreshed first, so the figures are exact for that range even
    when the scheduled refresh has not run yet.
    """
    since_value = _as_naive_utc(since) if since else datetime.now(timezone.utc).replace(tzinfo=None, minute=0, second=0, microsecond=0) - timedelta(days=7)
    until_value = _as_naive_utc(until) if until else _FAR_FUTURE
    db.execute(text("CALL sp_refresh_hourly_stats(:since)"), {"since": since_value})
    db.commit()  # keep the refreshed rollups; without this they are discarded when the request ends
    rows = db.execute(
        text(
            "SELECT s.agent_id, a.name AS agent_name, "
            "SUM(s.runs_total) AS runs_total, SUM(s.runs_completed) AS runs_completed, "
            "SUM(s.runs_failed) AS runs_failed, SUM(s.latency_sum_ms) AS latency_sum_ms, "
            "SUM(s.latency_count) AS latency_count, MAX(s.max_latency_ms) AS max_latency_ms "
            "FROM v_owned_hourly_stats s JOIN agents a ON a.id = s.agent_id "
            "WHERE s.bucket_start >= :since AND s.bucket_start < :until "
            "GROUP BY s.agent_id, a.name "
            "ORDER BY runs_total DESC, s.agent_id"
        ),
        {"since": since_value, "until": until_value},
    ).mappings().all()

    result = []
    for row in rows:
        total = int(row["runs_total"])
        failed = int(row["runs_failed"])
        latency_count = int(row["latency_count"] or 0)
        avg_latency = (float(row["latency_sum_ms"]) / latency_count) if latency_count else None
        result.append(
            AgentOverviewRow(
                agent_id=row["agent_id"],
                agent_name=row["agent_name"],
                runs_total=total,
                runs_completed=int(row["runs_completed"]),
                runs_failed=failed,
                failure_rate_pct=round(100.0 * failed / total, 2) if total else 0.0,
                avg_latency_ms=round(avg_latency, 2) if avg_latency is not None else None,
                max_latency_ms=int(row["max_latency_ms"]) if row["max_latency_ms"] is not None else None,
            )
        )
    return result
