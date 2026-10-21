from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.task import Task
    from app.models.run import Run
    from app.models.log import Log
    from app.models.alert import Alert


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("environment IN ('production', 'staging', 'development')", name="chk_agents_environment"),
        CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="chk_agents_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, server_default="production")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    version: Mapped[str] = mapped_column(String(20), nullable=False, server_default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="agents")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="agent")
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="agent", overlaps="task,runs,agent")
    logs: Mapped[List["Log"]] = relationship("Log", back_populates="agent")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="agent", cascade="all, delete-orphan")
