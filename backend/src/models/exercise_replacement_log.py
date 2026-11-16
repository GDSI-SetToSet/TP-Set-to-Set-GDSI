from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id


class ExerciseReplacementLog(Base):
    """US-54: reemplazo (o salto) de un ejercicio en la sesión del día; no modifica la rutina vigente."""

    __tablename__ = "exercise_replacement_logs"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "original_exercise_id",
            name="uq_exercise_replacement_session_exercise",
        ),
        Index(
            "ix_exercise_replacement_logs_legacy_lookup",
            "student_id",
            "routine_id",
            "day_name",
            "session_date",
            "original_exercise_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True, nullable=True
    )
    routine_id: Mapped[str] = mapped_column(String(36), nullable=False)
    day_name: Mapped[str] = mapped_column(String(100), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    original_exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), nullable=False)
    replacement_exercise_id: Mapped[str | None] = mapped_column(ForeignKey("exercises.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
