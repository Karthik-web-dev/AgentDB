from datetime import datetime
from typing import Optional
from sqlalchemy import Float, Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class AlertFiring(Base):
    """One row per rule firing. Written by the MySQL alert engine, never by the API.

    Exactly one source is set: metric_id for threshold rules, run_id for failure-window rules.
    """

    __tablename__ = "alert_firings"
    __table_args__ = (
        UniqueConstraint("alert_id", "metric_id", name="uq_alert_firings_alert_metric"),
        UniqueConstraint("alert_id", "run_id", name="uq_alert_firings_alert_run"),
        CheckConstraint("(metric_id IS NULL) + (run_id IS NULL) = 1", name="chk_alert_firings_one_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    metric_id: Mapped[Optional[int]] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), nullable=True)
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=True)
    observed_value: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float(precision=53), nullable=False)
    fired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    alert: Mapped["Alert"] = relationship("Alert")
