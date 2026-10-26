"""Modelo de certificado de apto médico del alumno (US-43).

Implementa la Alternativa A: historial acumulativo donde el certificado más
reciente es CURRENT y los anteriores quedan ARCHIVED para auditoría.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.user import new_id


class MedicalClearance(Base):
    __tablename__ = "medical_clearances"
    __table_args__ = (
        Index(
            "uq_medical_clearances_current",
            "student_id",
            unique=True,
            sqlite_where=text("status = 'CURRENT'"),
            postgresql_where=text("status = 'CURRENT'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 'CURRENT' = vigente; 'ARCHIVED' = versión anterior (Alternativa A)
    status: Mapped[str] = mapped_column(String(16), default="CURRENT", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    student: Mapped["StudentProfile"] = relationship(  # noqa: F821
        back_populates="medical_clearances"
    )
