from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ErrorSignature(Base):
    """A normalised, de-duplicated error message for one owner. Maintained by MySQL triggers (migration 008)."""

    __tablename__ = "error_signatures"
    __table_args__ = (
        UniqueConstraint("user_id", "signature_hash", name="uq_error_signatures_user_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_message: Mapped[str] = mapped_column(Text, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
