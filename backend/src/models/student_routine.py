from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id


class StudentRoutine(Base):
    """Copia por alumno de una rutina: contenido vigente y borrador (US-14).

    ponytail: días/bloques/ejercicios se guardan como JSON con la forma de RoutineTemplateInput;
    tablas hijas si hace falta consultar por ejercicio.
    """

    __tablename__ = "student_routines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    source_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(16), default="GENERIC", nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    intensity: Mapped[str] = mapped_column(String(16), nullable=False)
    has_no_materials_alternative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    desired_weekly_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days: Mapped[list] = mapped_column(JSON, nullable=False)
    draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    draft_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RoutineChangeLog(Base):
    """Registro inmutable de cada edición confirmada (sin delete, Principio IV análogo)."""

    __tablename__ = "routine_change_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_routine_id: Mapped[str] = mapped_column(
        ForeignKey("student_routines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trainer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
