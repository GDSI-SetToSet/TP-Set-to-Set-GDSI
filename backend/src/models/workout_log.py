from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (
        CheckConstraint(
            "rpe IS NULL OR (rpe >= 1 AND rpe <= 10)",
            name="ck_workout_sessions_rpe_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    routine_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    day_name: Mapped[str] = mapped_column(String(100), nullable=False)
    modality: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)


class WorkoutSetLog(Base):
    __tablename__ = "workout_set_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    routine_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    day_name: Mapped[str] = mapped_column(String(100), nullable=False)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True, nullable=False)
    exercise_name: Mapped[str] = mapped_column(String(150), nullable=False)
    modality: Mapped[str] = mapped_column(String(16), default="GYM", nullable=False)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_completed: Mapped[str] = mapped_column(String(50), nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Atributos transitorios para respuesta de API al registrar una serie
    is_personal_record: ClassVar[bool] = False
    is_initial_pr: ClassVar[bool] = False
    pr_previous_weight_kg: ClassVar[float | None] = None
