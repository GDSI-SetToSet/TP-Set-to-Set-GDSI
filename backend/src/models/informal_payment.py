"""Libro inmutable de pagos informales registrados por fuera de la app (US-34, Principio IV).

Los pagos no se eliminan: se anulan con motivo, fecha y usuario, y la corrección se
registra como un pago nuevo que referencia al anulado (``replaces_payment_id``).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base
from backend.src.models.user import new_id

PAYMENT_METHODS = ("EFECTIVO", "TRANSFERENCIA", "OTRO")
# PENDIENTE_CONFIRMACION y RECHAZADO quedan reservados para US-71 (pago informado por el alumno).
PAYMENT_STATUSES = ("PENDIENTE_CONFIRMACION", "CONFIRMADO", "RECHAZADO", "ANULADO")
PAYMENT_DELETE_FORBIDDEN = "Los pagos no se eliminan; se anulan."


class InformalPayment(Base):
    __tablename__ = "informal_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_informal_payments_amount"),
        CheckConstraint(
            "method IN ('EFECTIVO', 'TRANSFERENCIA', 'OTRO')",
            name="ck_informal_payments_method",
        ),
        CheckConstraint(
            "months_covered BETWEEN 1 AND 12",
            name="ck_informal_payments_months",
        ),
        CheckConstraint(
            "status IN ('PENDIENTE_CONFIRMACION', 'CONFIRMADO', 'RECHAZADO', 'ANULADO')",
            name="ck_informal_payments_status",
        ),
        CheckConstraint(
            "source IN ('TRAINER', 'STUDENT')",
            name="ck_informal_payments_source",
        ),
        CheckConstraint(
            "(status = 'RECHAZADO' AND rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL"
            " AND rejection_reason IS NOT NULL)"
            " OR (status <> 'RECHAZADO' AND rejected_at IS NULL AND rejected_by_user_id IS NULL"
            " AND rejection_reason IS NULL)",
            name="ck_informal_payments_reject_fields",
        ),
        CheckConstraint(
            "(status = 'ANULADO' AND voided_at IS NOT NULL AND voided_by_user_id IS NOT NULL"
            " AND void_reason IS NOT NULL)"
            " OR (status <> 'ANULADO' AND voided_at IS NULL AND voided_by_user_id IS NULL"
            " AND void_reason IS NULL)",
            name="ck_informal_payments_void_fields",
        ),
        UniqueConstraint("replaces_payment_id", name="uq_informal_payments_replaces"),
        Index("ix_informal_payments_relationship_status", "relationship_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Sin ON DELETE CASCADE: un vínculo con pagos no puede borrarse físicamente.
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id"), index=True, nullable=False
    )
    trainer_id: Mapped[str] = mapped_column(ForeignKey("trainer_profiles.id"), index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id"), index=True, nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    months_covered: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaces_payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("informal_payments.id"), nullable=True
    )
    # US-71: origen del registro y circuito de confirmación de pagos informados por el alumno.
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="TRAINER", server_default="TRAINER")
    confirmed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receipt_size: Mapped[int | None] = mapped_column(Integer, nullable=True)


@event.listens_for(InformalPayment, "before_delete")
def _forbid_payment_delete(mapper, connection, target) -> None:
    raise RuntimeError(PAYMENT_DELETE_FORBIDDEN)
