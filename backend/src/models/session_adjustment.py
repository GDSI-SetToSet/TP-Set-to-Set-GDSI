from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id


class SessionAdjustment(Base):
    """US-26: ajuste del entrenador a un día de rutina a partir de una sesión finalizada.

    PENDING: el alumno estaba entrenando al guardarlo; se aplica al terminar esa sesión (o al iniciar otra).
    APPLIED: ya está en la rutina; el alumno ve la marca hasta finalizar una sesión de ese día.
    SUPERSEDED: lo reemplazó un ajuste posterior del mismo día, o el día dejó de existir.
    """

    __tablename__ = "session_adjustments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # None mientras está pendiente y el alumno todavía no tiene copia de la rutina (se crea al aplicar).
    student_routine_id: Mapped[str | None] = mapped_column(
        ForeignKey("student_routines.id", ondelete="CASCADE"), index=True, nullable=True
    )
    source_session_id: Mapped[str] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    blocking_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trainer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    day_name: Mapped[str] = mapped_column(String(100), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    blocks: Mapped[list] = mapped_column(JSON, nullable=False)
    changed_exercise_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
