from datetime import datetime
from decimal import Decimal

from backend.src.core.database import Base
from backend.src.models.user import new_id
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class TrainingRequest(Base):
    __tablename__ = "training_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trainer_id: Mapped[str] = mapped_column(
        ForeignKey("trainer_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("training_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agreed_monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    agreed_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    student_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trainer_response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped["StudentProfile"] = relationship()  # noqa: F821
    trainer: Mapped["TrainerProfile"] = relationship()  # noqa: F821
    plan: Mapped["TrainingPlan"] = relationship()  # noqa: F821
