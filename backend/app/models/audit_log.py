from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base):
    """Append-only audit record.

    The hash-chain columns (chain_seq, prev_hash, row_hash) are written only by the
    BEFORE INSERT trigger in database/migrations/001_audit_hash_chain.sql. The API never
    sets them, and rows that carry them can never be updated or deleted.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    # Hash chain (maintained by MySQL triggers, read-only from Python)
    chain_seq: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, unique=True)
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    row_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
