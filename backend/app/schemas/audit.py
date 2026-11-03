"""Audit trail schemas, including the hash-chain fields used for verification."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: Optional[int]
    details: Optional[Any]
    timestamp: datetime
    chain_seq: Optional[int]
    prev_hash: Optional[str]
    row_hash: Optional[str]

    model_config = {"from_attributes": True}


class ChainVerification(BaseModel):
    """Result of sp_verify_audit_chain()."""

    is_valid: bool
    rows_checked: int
    first_broken_seq: Optional[int]
    message: str
