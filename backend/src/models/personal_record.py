from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.user import new_id


class PersonalRecord(Base):
    __tablename__ = "personal_records"
    __table_args__ = (
        UniqueConstraint("student_id", "exercise_id", name="uq_personal_records_student_exercise"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exercise_id: Mapped[str] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True, nullable=False
    )
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    reps_completed: Mapped[str] = mapped_column(String(50), nullable=False)
    workout_set_log_id: Mapped[str] = mapped_column(
        ForeignKey("workout_set_logs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    student: Mapped["StudentProfile"] = relationship()  # noqa: F821
    exercise: Mapped["Exercise"] = relationship()  # noqa: F821
    workout_set_log: Mapped["WorkoutSetLog"] = relationship()  # noqa: F821
