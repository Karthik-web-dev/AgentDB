from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.agent import Agent


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("condition_operator IN ('>', '>=', '<', '<=', '==', '!=')", name="chk_alerts_operator"),
        CheckConstraint("status IN ('active', 'triggered', 'disabled', 'resolved')", name="chk_alerts_status"),
        CheckConstraint("rule_type IN ('threshold', 'failure_window')", name="chk_alerts_rule_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="threshold")
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_operator: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    time_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="alerts")
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="alerts")
