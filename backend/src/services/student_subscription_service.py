"""Suscripción vista por el alumno, pagos informados con comprobante y bloqueo por vencimiento (US-71).

El vencimiento sale de los pagos CONFIRMADO (US-34): un pago informado queda PENDIENTE_CONFIRMACION
y no lo extiende hasta que el entrenador lo confirma.
"""

from datetime import UTC, date, datetime

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.core.storage import (
    RECEIPTS_DIR,
    StorageError,
    open_upload,
    save_upload,
)
from backend.src.models.informal_payment import InformalPayment
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.informal_payment import (
    PAID_ON_FUTURE_MESSAGE,
    PaymentCreate,
    PaymentHistory,
    PaymentMutationResult,
    SubscriptionSummary,
)
from backend.src.services.informal_payment_service import (
    PENDING,
    PaymentError,
    payment_views,
    relationship_payments,
    relationship_summary,
    single_view,
)
from backend.src.services.notification_service import create_notification
from backend.src.services.subscription_service import STATUS_ORDER, current_date

ONLY_STUDENTS = "Esta acción está disponible solo para alumnos."
NOT_FOUND = "No se encontró la suscripción."
RECEIPT_NOT_FOUND = "No se encontró el comprobante."
EXPIRED_BLOCK = (
    "Tu suscripción está vencida: informá tu pago para que tu entrenador lo confirme y puedas volver a entrenar."
)
PAYMENT_REPORTED = "PAYMENT_REPORTED"


def _student_relationship(db: Session, user: User, relationship_id: str) -> TrainingRelationship:
    if user.role != STUDENT_ROLE:
        raise PaymentError(403, ONLY_STUDENTS)
    relationship = db.get(TrainingRelationship, relationship_id)
    profile = user.student_profile
    if relationship is None or profile is None or relationship.student_id != profile.id or relationship.status != "ACTIVE":
        raise PaymentError(404, NOT_FOUND)
    return relationship


def list_student_subscriptions(db: Session, user: User, today: date) -> list[SubscriptionSummary]:
    """Escenarios 1, 2 y 4: una suscripción por vínculo activo, las vencidas primero."""
    if user.role != STUDENT_ROLE:
        raise PaymentError(403, ONLY_STUDENTS)
    if user.student_profile is None:
        return []
    relationships = db.scalars(
        select(TrainingRelationship).where(
            TrainingRelationship.student_id == user.student_profile.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    result = [relationship_summary(db, relationship, today) for relationship in relationships]
    result.sort(key=lambda item: (STATUS_ORDER[item.status], item.due_date, item.trainer_name.lower()))
    return result


def get_student_payment_history(db: Session, user: User, relationship_id: str, today: date) -> PaymentHistory:
    """Escenario 5: todos los pagos del vínculo con su estado."""
    relationship = _student_relationship(db, user, relationship_id)
    return PaymentHistory(
        subscription=relationship_summary(db, relationship, today),
        payments=payment_views(db, relationship_payments(db, relationship.id)),
    )


async def report_payment(
    db: Session,
    user: User,
    relationship_id: str,
    data: PaymentCreate,
    receipt: UploadFile | None,
    today: date,
) -> PaymentMutationResult:
    """Escenario 3: el alumno informa un pago; queda pendiente de confirmación y se avisa al entrenador."""
    relationship = _student_relationship(db, user, relationship_id)
    if data.paid_on > today:
        raise PaymentError(422, "Los datos del pago no son válidos.", [{"field": "paid_on", "message": PAID_ON_FUTURE_MESSAGE}])

    receipt_fields: dict[str, object] = {}
    if receipt is not None and receipt.filename:
        try:
            path, size = await save_upload(relationship.id, receipt, base=RECEIPTS_DIR)
        except StorageError as error:
            raise PaymentError(422, error.message, [{"field": "receipt", "message": error.message}]) from error
        receipt_fields = {
            "receipt_path": path,
            "receipt_filename": receipt.filename[:255],
            "receipt_mime_type": receipt.content_type,
            "receipt_size": size,
        }

    payment = InformalPayment(
        relationship_id=relationship.id,
        trainer_id=relationship.trainer_id,
        student_id=relationship.student_id,
        paid_on=data.paid_on,
        amount=data.amount,
        currency=relationship.agreed_currency,
        method=data.method,
        months_covered=data.months_covered,
        status=PENDING,
        note=data.note,
        registered_by_user_id=user.id,
        source="STUDENT",
        created_at=datetime.now(UTC).replace(tzinfo=None),
        **receipt_fields,
    )
    db.add(payment)
    db.flush()
    summary = relationship_summary(db, relationship, today)
    trainer_user_id = relationship.trainer.user_id
    create_notification(
        db,
        recipient_id=trainer_user_id,
        type=PAYMENT_REPORTED,
        title=f"{summary.student_name} informó un pago"[:150],
        message=f"Pago del {data.paid_on.strftime('%d/%m/%Y')} por {data.amount} {relationship.agreed_currency} "
        f"({data.months_covered} {'mes' if data.months_covered == 1 else 'meses'}). Revisalo para confirmarlo.",
        related_entity_type="InformalPayment",
        related_entity_id=payment.id,
        related_student_id=relationship.student_id,
    )
    db.commit()
    db.refresh(payment)
    return PaymentMutationResult(subscription=relationship_summary(db, relationship, today), payment=single_view(db, payment))


def receipt_for_download(db: Session, user: User, payment_id: str) -> tuple[InformalPayment, object]:
    """Comprobante privado: solo el alumno y el entrenador del vínculo (404 para cualquier otro)."""
    payment = db.get(InformalPayment, payment_id)
    relationship = db.get(TrainingRelationship, payment.relationship_id) if payment else None
    allowed = False
    if payment is not None and relationship is not None:
        if user.role == STUDENT_ROLE and user.student_profile is not None:
            allowed = relationship.student_id == user.student_profile.id
        elif user.role == TRAINER_ROLE and user.trainer_profile is not None:
            allowed = relationship.trainer_id == user.trainer_profile.id and relationship.status == "ACTIVE"
    if not allowed or not payment.receipt_path:
        raise PaymentError(404, RECEIPT_NOT_FOUND)
    try:
        path = open_upload(payment.receipt_path, base=RECEIPTS_DIR, not_found=RECEIPT_NOT_FOUND)
    except StorageError as error:
        raise PaymentError(404, RECEIPT_NOT_FOUND) from error
    return payment, path


def is_subscription_expired(db: Session, relationship: TrainingRelationship) -> bool:
    """FR-006: con la suscripción vencida no se inician sesiones nuevas. Un pago pendiente no desbloquea."""
    return relationship_summary(db, relationship, current_date()).status == "VENCIDA"
