from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.run import Run
    from app.models.agent import Agent


class Log(Base):
    __tablename__ = "logs"
    __table_args__ = (
        CheckConstraint("severity IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name="chk_logs_severity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[Any]] = mapped_column("metadata", JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="logs")
    agent: Mapped["Agent"] = relationship("Agent", back_populates="logs")
