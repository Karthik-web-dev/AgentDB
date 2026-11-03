from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AgentMemory(Base):
    """Conversation turns retained for an agent and supplied to later model calls."""

    __tablename__ = "agent_memory"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="chk_agent_memory_role"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="RESTRICT"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class AgentMemorySummary(Base):
    """Bounded model-generated summary of older turns; source messages remain untouched."""

    __tablename__ = "agent_memory_summaries"

    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"), primary_key=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summarized_through_id: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
