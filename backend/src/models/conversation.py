"""Mensajes entrenador–alumno (US-21) y consultas técnicas con notas fijadas (US-62).

La conversación es el vínculo de entrenamiento: no hay tabla de conversaciones.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id

MESSAGE_KINDS = ("TEXT", "TECHNICAL_QUERY")
SENDER_ROLES = ("TRAINER", "STUDENT")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("sender_role IN ('TRAINER', 'STUDENT')", name="ck_conversation_messages_sender_role"),
        CheckConstraint("kind IN ('TEXT', 'TECHNICAL_QUERY')", name="ck_conversation_messages_kind"),
        CheckConstraint(
            "kind <> 'TECHNICAL_QUERY' OR exercise_name IS NOT NULL",
            name="ck_conversation_messages_query_exercise",
        ),
        CheckConstraint(
            "reply_to_message_id IS NULL OR kind = 'TEXT'",
            name="ck_conversation_messages_reply_kind",
        ),
        Index("ix_conversation_messages_relationship_created", "relationship_id", "created_at"),
        Index("ix_conversation_messages_reply_to", "reply_to_message_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"), nullable=False
    )
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sender_role: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="TEXT")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Copia del nombre: la tarjeta de la consulta sobrevive si el ejercicio se elimina.
    exercise_id: Mapped[str | None] = mapped_column(ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True)
    exercise_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    set_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_to_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TechnicalNote(Base):
    """Respuesta fijada que el alumno debe confirmar al iniciar el ejercicio en su próxima sesión."""

    __tablename__ = "technical_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    exercise_id: Mapped[str | None] = mapped_column(ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True)
    exercise_name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
