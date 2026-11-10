"""Devolución del entrenador sobre el esfuerzo reportado en una sesión (US-64)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.user import new_id

EFFORT_FEEDBACK_CATEGORIES = ("MORE_EFFORT", "ADEQUATE", "LESS_INTENSITY")


class EffortFeedback(Base):
    __tablename__ = "workout_effort_feedback"
    __table_args__ = (
        CheckConstraint(
            "category IN ('MORE_EFFORT', 'ADEQUATE', 'LESS_INTENSITY')",
            name="ck_workout_effort_feedback_category",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trainer_id: Mapped[str] = mapped_column(ForeignKey("trainer_profiles.id"), index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["WorkoutSession"] = relationship()  # noqa: F821
