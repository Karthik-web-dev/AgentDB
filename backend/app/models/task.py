from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.run import Run


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("id", "agent_id", name="uq_tasks_id_agent"),
        CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')", name="chk_tasks_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="chk_tasks_priority"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="tasks")
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="task", overlaps="agent,runs,task")
