from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.user import new_id


class TrainingRelationship(Base):
    __tablename__ = "training_relationships"
    __table_args__ = (
        Index(
            "uq_active_training_relationship",
            "student_id",
            "trainer_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

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
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    welcome_message_sent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    initial_routine_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped["StudentProfile"] = relationship()  # noqa: F821
    trainer: Mapped["TrainerProfile"] = relationship()  # noqa: F821
    plan: Mapped["TrainingPlan"] = relationship()  # noqa: F821
