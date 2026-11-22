"""Registro, anulación e historial de pagos informales del entrenador (US-34).

Los pagos son inmutables (Principio IV): solo se anulan con motivo, fecha y usuario, y la
corrección es un pago nuevo que referencia al anulado. El vencimiento se calcula con
``subscription_service`` a partir de los pagos CONFIRMADO, así que una anulación lo recalcula sola.
"""

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.src.models.informal_payment import InformalPayment
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.informal_payment import (
    PAID_ON_FUTURE_MESSAGE,
    PaymentCreate,
    PaymentHistory,
    PaymentMutationResult,
    PaymentView,
    SubscriptionSummary,
)
from backend.src.services.notification_service import create_notification
from backend.src.services.subscription_service import (
    STATUS_ORDER,
    compute_due_date,
    subscription_status,
)
from backend.src.services.trainer_student_service import (
    TrainerStudentError,
    _active_relationship,
    _trainer_profile,
)

CONFIRMED = "CONFIRMADO"
VOIDED = "ANULADO"
PENDING = "PENDIENTE_CONFIRMACION"
REJECTED = "RECHAZADO"
ONLY_CONFIRMED_VOID = "Solo se pueden anular pagos confirmados."
NOT_PENDING = "El pago no está pendiente de confirmación."
PAYMENT_NOT_FOUND = "No se encontró el pago."
ALREADY_VOIDED = "El pago ya está anulado."
REPLACES_INVALID = "Solo se puede corregir un pago anulado del mismo alumno."
REPLACES_TAKEN = "El pago anulado ya tiene un pago corregido."


class PaymentError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _trainer(db: Session, user: User) -> TrainerProfile:
    try:
        return _trainer_profile(db, user)
    except TrainerStudentError as error:
        raise PaymentError(error.status_code, error.detail) from error


def _relationship(db: Session, trainer: TrainerProfile, student_id: str) -> TrainingRelationship:
    try:
        return _active_relationship(db, trainer.id, student_id)
    except TrainerStudentError as error:
        raise PaymentError(error.status_code, error.detail) from error


def _student_name(student: StudentProfile, email: str) -> str:
    name = " ".join(part for part in (student.first_name, student.last_name) if part).strip()
    return name or email


def _confirmed_totals(db: Session, relationship_ids: list[str]) -> dict[str, tuple[int, date | None]]:
    """Una sola consulta: meses confirmados y último pago por vínculo."""
    if not relationship_ids:
        return {}
    rows = db.execute(
        select(
            InformalPayment.relationship_id,
            func.coalesce(func.sum(InformalPayment.months_covered), 0),
            func.max(InformalPayment.paid_on),
        )
        .where(
            InformalPayment.relationship_id.in_(relationship_ids),
            InformalPayment.status == CONFIRMED,
        )
        .group_by(InformalPayment.relationship_id)
    ).all()
    return {rel_id: (int(months), last_paid) for rel_id, months, last_paid in rows}


def _pending_counts(db: Session, relationship_ids: list[str]) -> dict[str, int]:
    """US-71: pagos informados por el alumno que esperan confirmación, por vínculo."""
    if not relationship_ids:
        return {}
    rows = db.execute(
        select(InformalPayment.relationship_id, func.count(InformalPayment.id))
        .where(InformalPayment.relationship_id.in_(relationship_ids), InformalPayment.status == PENDING)
        .group_by(InformalPayment.relationship_id)
    ).all()
    return {rel_id: int(count) for rel_id, count in rows}


def _trainer_name(db: Session, relationship: TrainingRelationship) -> str:
    trainer = db.get(TrainerProfile, relationship.trainer_id)
    trainer_user = db.get(User, trainer.user_id) if trainer else None
    return ((trainer.full_name or "").strip() if trainer else "") or (trainer_user.email if trainer_user else "")


def _summary(
    relationship: TrainingRelationship,
    student_name: str,
    totals: tuple[int, date | None],
    today: date,
    *,
    trainer_name: str = "",
    pending_payment_count: int = 0,
) -> SubscriptionSummary:
    months_paid, last_payment_on = totals
    due_date = compute_due_date(relationship.start_date, months_paid)
    status, days_until_due = subscription_status(due_date, today)
    return SubscriptionSummary(
        relationship_id=relationship.id,
        student_id=relationship.student_id,
        student_name=student_name,
        plan_id=relationship.plan_id,
        plan_title=relationship.plan.title if relationship.plan else "",
        agreed_monthly_price=relationship.agreed_monthly_price,
        currency=relationship.agreed_currency,
        start_date=relationship.start_date,
        months_paid=months_paid,
        due_date=due_date,
        days_until_due=days_until_due,
        status=status,
        last_payment_on=last_payment_on,
        trainer_id=relationship.trainer_id,
        trainer_name=trainer_name,
        pending_payment_count=pending_payment_count,
    )


def relationship_summary(db: Session, relationship: TrainingRelationship, today: date) -> SubscriptionSummary:
    student = db.get(StudentProfile, relationship.student_id)
    student_user = db.get(User, student.user_id) if student else None
    name = _student_name(student, student_user.email if student_user else "") if student else ""
    totals = _confirmed_totals(db, [relationship.id]).get(relationship.id, (0, None))
    return _summary(
        relationship,
        name,
        totals,
        today,
        trainer_name=_trainer_name(db, relationship),
        pending_payment_count=_pending_counts(db, [relationship.id]).get(relationship.id, 0),
    )



def list_subscriptions(
    db: Session, user: User, today: date, status: str | None = None
) -> list[SubscriptionSummary]:
    """Escenario 1: suscripciones de los alumnos activos, vencidas primero."""
    trainer = _trainer(db, user)
    rows = db.execute(
        select(TrainingRelationship, StudentProfile, User)
        .join(StudentProfile, TrainingRelationship.student_id == StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
    ).all()
    relationship_ids = [relationship.id for relationship, _, _ in rows]
    totals = _confirmed_totals(db, relationship_ids)
    pending = _pending_counts(db, relationship_ids)
    trainer_name = (trainer.full_name or "").strip() or user.email
    result = [
        _summary(
            relationship,
            _student_name(student, student_user.email),
            totals.get(relationship.id, (0, None)),
            today,
            trainer_name=trainer_name,
            pending_payment_count=pending.get(relationship.id, 0),
        )
        for relationship, student, student_user in rows
    ]
    if status is not None:
        result = [item for item in result if item.status == status]
    result.sort(key=lambda item: (STATUS_ORDER[item.status], item.due_date, item.student_name.lower()))
    return result


def _display_names(db: Session, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, User.email, TrainerProfile.full_name, StudentProfile.first_name, StudentProfile.last_name)
        .outerjoin(TrainerProfile, TrainerProfile.user_id == User.id)
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .where(User.id.in_(user_ids))
    ).all()
    names = {}
    for user_id, email, full_name, first_name, last_name in rows:
        student_name = " ".join(part for part in (first_name, last_name) if part).strip()
        names[user_id] = (full_name or "").strip() or student_name or email
    return names


def payment_views(db: Session, payments: list[InformalPayment]) -> list[PaymentView]:
    user_ids = {p.registered_by_user_id for p in payments} | {
        uid for p in payments for uid in (p.voided_by_user_id, p.confirmed_by_user_id, p.rejected_by_user_id) if uid
    }
    names = _display_names(db, user_ids)
    replaced_by = {p.replaces_payment_id: p.id for p in payments if p.replaces_payment_id}
    return [
        PaymentView(
            id=p.id,
            paid_on=p.paid_on,
            amount=p.amount,
            currency=p.currency,
            method=p.method,
            months_covered=p.months_covered,
            status=p.status,
            note=p.note,
            registered_by_name=names.get(p.registered_by_user_id, ""),
            created_at=p.created_at,
            voided_at=p.voided_at,
            voided_by_name=names.get(p.voided_by_user_id) if p.voided_by_user_id else None,
            void_reason=p.void_reason,
            replaces_payment_id=p.replaces_payment_id,
            replaced_by_payment_id=replaced_by.get(p.id),
            source=p.source or "TRAINER",
            confirmed_by_name=names.get(p.confirmed_by_user_id) if p.confirmed_by_user_id else None,
            confirmed_at=p.confirmed_at,
            rejected_by_name=names.get(p.rejected_by_user_id) if p.rejected_by_user_id else None,
            rejected_at=p.rejected_at,
            rejection_reason=p.rejection_reason,
            has_receipt=bool(p.receipt_path),
            receipt_filename=p.receipt_filename,
        )
        for p in payments
    ]


def relationship_payments(db: Session, relationship_id: str) -> list[InformalPayment]:
    return list(
        db.scalars(
            select(InformalPayment)
            .where(InformalPayment.relationship_id == relationship_id)
            .order_by(InformalPayment.paid_on.desc(), InformalPayment.created_at.desc())
        )
    )


def single_view(db: Session, payment: InformalPayment) -> PaymentView:
    views = payment_views(db, relationship_payments(db, payment.relationship_id))
    return next(view for view in views if view.id == payment.id)


def get_payment_history(db: Session, user: User, student_id: str, today: date) -> PaymentHistory:
    """Escenario 5: suscripción e historial completo, incluidos los anulados."""
    trainer = _trainer(db, user)
    relationship = _relationship(db, trainer, student_id)
    payments = relationship_payments(db, relationship.id)
    return PaymentHistory(
        subscription=relationship_summary(db, relationship, today),
        payments=payment_views(db, payments),
    )


def register_payment(
    db: Session, user: User, student_id: str, data: PaymentCreate, today: date
) -> PaymentMutationResult:
    """Escenarios 2, 3 y 6: registra un pago CONFIRMADO que extiende el vencimiento."""
    trainer = _trainer(db, user)
    if data.paid_on > today:
        raise PaymentError(
            422,
            "Los datos del pago no son válidos.",
            [{"field": "paid_on", "message": PAID_ON_FUTURE_MESSAGE}],
        )
    relationship = _relationship(db, trainer, student_id)

    if data.replaces_payment_id is not None:
        original = db.get(InformalPayment, data.replaces_payment_id)
        if original is None or original.relationship_id != relationship.id or original.status != VOIDED:
            raise PaymentError(
                422,
                REPLACES_INVALID,
                [{"field": "replaces_payment_id", "message": REPLACES_INVALID}],
            )
        already = db.scalar(
            select(InformalPayment.id).where(InformalPayment.replaces_payment_id == original.id)
        )
        if already is not None:
            raise PaymentError(409, REPLACES_TAKEN)

    payment = InformalPayment(
        relationship_id=relationship.id,
        trainer_id=trainer.id,
        student_id=relationship.student_id,
        paid_on=data.paid_on,
        amount=data.amount,
        currency=relationship.agreed_currency,
        method=data.method,
        months_covered=data.months_covered,
        status=CONFIRMED,
        note=data.note,
        registered_by_user_id=user.id,
        created_at=_utc_now(),
        replaces_payment_id=data.replaces_payment_id,
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # Carrera entre dos correcciones simultáneas del mismo pago (UNIQUE replaces_payment_id).
        raise PaymentError(409, REPLACES_TAKEN) from error
    db.refresh(payment)
    return PaymentMutationResult(
        subscription=relationship_summary(db, relationship, today),
        payment=single_view(db, payment),
    )


def void_payment(
    db: Session, user: User, payment_id: str, reason: str, today: date
) -> PaymentMutationResult:
    """Escenarios 5 y 6: anula un pago con motivo; nunca lo borra."""
    trainer = _trainer(db, user)
    payment = db.get(InformalPayment, payment_id)
    if payment is None or payment.trainer_id != trainer.id:
        raise PaymentError(404, PAYMENT_NOT_FOUND)
    relationship = db.get(TrainingRelationship, payment.relationship_id)
    if relationship is None or relationship.status != "ACTIVE":
        raise PaymentError(404, PAYMENT_NOT_FOUND)
    if payment.status == VOIDED:
        raise PaymentError(409, ALREADY_VOIDED)
    if payment.status != CONFIRMED:
        # US-71: un pago informado pendiente se confirma o se rechaza; uno rechazado ya está cerrado.
        raise PaymentError(409, ONLY_CONFIRMED_VOID)

    payment.status = VOIDED
    payment.voided_at = _utc_now()
    payment.voided_by_user_id = user.id
    payment.void_reason = reason
    db.commit()
    db.refresh(payment)
    return PaymentMutationResult(
        subscription=relationship_summary(db, relationship, today),
        payment=single_view(db, payment),
    )


def _pending_payment_of_trainer(db: Session, user: User, payment_id: str) -> tuple[InformalPayment, TrainingRelationship]:
    trainer = _trainer(db, user)
    payment = db.get(InformalPayment, payment_id)
    if payment is None or payment.trainer_id != trainer.id:
        raise PaymentError(404, PAYMENT_NOT_FOUND)
    relationship = db.get(TrainingRelationship, payment.relationship_id)
    if relationship is None or relationship.status != "ACTIVE":
        raise PaymentError(404, PAYMENT_NOT_FOUND)
    if payment.status != PENDING:
        raise PaymentError(409, NOT_PENDING)
    return payment, relationship


def _notify_student(db: Session, relationship: TrainingRelationship, kind: str, title: str, message: str, payment_id: str) -> None:
    student = db.get(StudentProfile, relationship.student_id)
    create_notification(
        db,
        recipient_id=student.user_id,
        type=kind,
        title=title,
        message=message,
        related_entity_type="InformalPayment",
        related_entity_id=payment_id,
        related_student_id=relationship.student_id,
    )


def confirm_payment(db: Session, user: User, payment_id: str, today: date) -> PaymentMutationResult:
    """US-71 escenario 6: confirma un pago informado; extiende el vencimiento."""
    payment, relationship = _pending_payment_of_trainer(db, user, payment_id)
    payment.status = CONFIRMED
    payment.confirmed_at = _utc_now()
    payment.confirmed_by_user_id = user.id
    db.flush()
    summary = relationship_summary(db, relationship, today)
    _notify_student(
        db,
        relationship,
        "PAYMENT_CONFIRMED",
        "Tu entrenador confirmó tu pago",
        f"Pago del {payment.paid_on.strftime('%d/%m/%Y')} confirmado. Tu suscripción vence el {summary.due_date.strftime('%d/%m/%Y')}.",
        payment.id,
    )
    db.commit()
    db.refresh(payment)
    return PaymentMutationResult(subscription=relationship_summary(db, relationship, today), payment=single_view(db, payment))


def reject_payment(db: Session, user: User, payment_id: str, reason: str, today: date) -> PaymentMutationResult:
    """US-71 escenario 6: rechaza un pago informado con motivo; el vencimiento no cambia."""
    payment, relationship = _pending_payment_of_trainer(db, user, payment_id)
    payment.status = REJECTED
    payment.rejected_at = _utc_now()
    payment.rejected_by_user_id = user.id
    payment.rejection_reason = reason
    _notify_student(
        db,
        relationship,
        "PAYMENT_REJECTED",
        "Tu entrenador rechazó un pago informado",
        f"Pago del {payment.paid_on.strftime('%d/%m/%Y')}. Motivo: {reason}",
        payment.id,
    )
    db.commit()
    db.refresh(payment)
    return PaymentMutationResult(subscription=relationship_summary(db, relationship, today), payment=single_view(db, payment))
