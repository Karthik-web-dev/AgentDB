"""Audit trail API: read the caller's audit records and verify the global hash chain."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogResponse, ChainVerification

router = APIRouter(prefix=f"{settings.API_V1_STR}/audit", tags=["Audit"])


@router.get("", response_model=List[AuditLogResponse])
def list_audit_records(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AuditLogResponse]:
    """Audit records attributed to the current user, newest first."""
    stmt = select(AuditLog).where(AuditLog.user_id == current_user.id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    stmt = stmt.order_by(AuditLog.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/verify", response_model=ChainVerification)
def verify_audit_chain(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChainVerification:
    """Recompute the whole audit hash chain inside MySQL and report whether it is intact.

    The chain is global (it covers every user's records), so this reports system-wide integrity.
    """
    db.execute(text("CALL sp_verify_audit_chain(@audit_valid, @audit_checked, @audit_broken)"))
    valid, checked, broken = db.execute(
        text("SELECT @audit_valid, @audit_checked, @audit_broken")
    ).one()
    is_valid = bool(valid)
    if is_valid:
        message = f"Audit chain intact: {checked} record(s) verified."
    else:
        message = f"Audit chain BROKEN at chain position {broken}. Records from that point are not trustworthy."
    return ChainVerification(
        is_valid=is_valid,
        rows_checked=int(checked or 0),
        first_broken_seq=int(broken) if broken is not None else None,
        message=message,
    )
