"""Logros del alumno (US-67) y felicitaciones del entrenador.

Los logros se calculan a partir de las sesiones, los récords y la racha, y se guardan al
desbloquearse para conservar la fecha real y no perderse nunca.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id


class StudentAchievement(Base):
    __tablename__ = "student_achievements"
    __table_args__ = (UniqueConstraint("student_id", "code", name="uq_student_achievements_student_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    # Fecha real en que se alcanzó el hito.
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Hitos cumplidos antes de la funcionalidad: sin celebración ni aviso al entrenador.
    retroactive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    celebrated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AchievementCongratulation(Base):
    __tablename__ = "achievement_congratulations"
    __table_args__ = (
        UniqueConstraint(
            "achievement_id",
            "trainer_id",
            name="uq_achievement_congratulations_achievement_trainer",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    achievement_id: Mapped[str] = mapped_column(
        ForeignKey("student_achievements.id", ondelete="CASCADE"), nullable=False
    )
    trainer_id: Mapped[str] = mapped_column(ForeignKey("trainer_profiles.id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
