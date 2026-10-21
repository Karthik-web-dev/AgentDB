from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, ForeignKeyConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.task import Task
    from app.models.event import Event
    from app.models.log import Log
    from app.models.metric import Metric
    from app.models.error_signature import ErrorSignature


class Run(Base):
    """One execution of an agent.

    parent_run_id links a sub-run to the run that started it (trace tree, migration 007).
    error_signature_id is maintained by the database from error_message (migration 008).
    Both are read-only from the application's point of view.
    """

    __tablename__ = "runs"
    __table_args__ = (
        ForeignKeyConstraint(["agent_id"], ["agents.id"], name="fk_runs_agent", ondelete="RESTRICT"),
        ForeignKeyConstraint(["task_id", "agent_id"], ["tasks.id", "tasks.agent_id"], name="fk_runs_task_agent", ondelete="RESTRICT"),
        CheckConstraint("status IN ('running', 'completed', 'failed', 'cancelled')", name="chk_runs_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    agent_id: Mapped[int] = mapped_column(nullable=False)
    parent_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("runs.id", ondelete="RESTRICT"), nullable=True)
    error_signature_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("error_signatures.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="runs", foreign_keys=[agent_id], overlaps="task,runs")
    task: Mapped[Optional["Task"]] = relationship("Task", back_populates="runs", foreign_keys=[task_id], overlaps="agent,runs")
    error_signature: Mapped[Optional["ErrorSignature"]] = relationship("ErrorSignature", foreign_keys=[error_signature_id])
    events: Mapped[List["Event"]] = relationship("Event", back_populates="run", cascade="all, delete-orphan")
    logs: Mapped[List["Log"]] = relationship("Log", back_populates="run", cascade="all, delete-orphan")
    metrics: Mapped[List["Metric"]] = relationship("Metric", back_populates="run", cascade="all, delete-orphan")
