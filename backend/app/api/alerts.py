"""Alert rule management API.

Rules are stored here, but firings are never written by the API: sp_evaluate_metric_alerts()
(database/migrations/002_alert_engine.sql) evaluates every new metric inside MySQL.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.agent import Agent
from app.models.alert import Alert
from app.models.alert_firing import AlertFiring
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertFiringResponse, AlertResponse, AlertUpdate

router = APIRouter(prefix=f"{settings.API_V1_STR}/alerts", tags=["Alerts"])


def _get_owned_alert(db: Session, alert_id: int, current_user: User) -> Alert:
    """Return the alert if the current user owns it, else 404 (no existence leak)."""
    alert = db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    return alert


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """Create an alert rule. A rule with agent_id targets one agent you own; without it, the rule covers all your agents."""
    if payload.agent_id is not None:
        owned = db.execute(
            select(Agent.id).where(Agent.id == payload.agent_id, Agent.user_id == current_user.id)
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found or not owned by user.")

    alert = Alert(
        user_id=current_user.id,
        agent_id=payload.agent_id,
        rule_name=payload.rule_name,
        rule_type=payload.rule_type,
        metric_name=payload.metric_name,
        condition_operator=payload.condition_operator,
        threshold_value=payload.threshold_value,
        time_window_minutes=payload.time_window_minutes,
        status="active",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("", response_model=List[AlertResponse])
def list_alerts(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AlertResponse]:
    """List the current user's alert rules, optionally filtered by status."""
    stmt = select(Alert).where(Alert.user_id == current_user.id)
    if status_filter is not None:
        stmt = stmt.where(Alert.status == status_filter)
    stmt = stmt.order_by(Alert.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    return _get_owned_alert(db, alert_id, current_user)


@router.patch("/{alert_id}", response_model=AlertResponse)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """Partially update a rule. Only the fields you send are changed."""
    alert = _get_owned_alert(db, alert_id, current_user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, key, value)
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    """Mark a rule as resolved. Resolved rules no longer fire until re-activated with PATCH."""
    alert = _get_owned_alert(db, alert_id, current_user)
    alert.status = "resolved"
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/{alert_id}/firings", response_model=List[AlertFiringResponse])
def list_alert_firings(
    alert_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AlertFiringResponse]:
    """History of every time this rule matched a metric, newest first."""
    _get_owned_alert(db, alert_id, current_user)
    stmt = (
        select(AlertFiring)
        .where(AlertFiring.alert_id == alert_id)
        .order_by(AlertFiring.fired_at.desc(), AlertFiring.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a rule and its firing history (firings cascade with the rule)."""
    alert = _get_owned_alert(db, alert_id, current_user)
    db.delete(alert)
    db.commit()
    return None
