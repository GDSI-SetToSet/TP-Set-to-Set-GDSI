"""Baja de un alumno por parte del entrenador (US-35).

El vínculo pasa a TERMINATED. Todo lo demás (cupo, "Mis alumnos", suscripciones, acceso a
datos de salud, rutina del alumno y chat) ya filtra por vínculo ACTIVE, así que reacciona solo.
Los pagos y los mensajes no se borran.
"""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from backend.src.models.user import User
from backend.src.schemas.trainer_student import (
    TERMINATION_CATEGORY_LABELS,
    StudentTerminationRequest,
    StudentTerminationResult,
)
from backend.src.services.conversation_service import parties, preview
from backend.src.services.notification_service import create_notification
from backend.src.services.trainer_service import quota_summary
from backend.src.services.trainer_student_service import (
    _active_relationship,
    _trainer_profile,
)

SUBSCRIPTION_TERMINATED = "SUBSCRIPTION_TERMINATED"


def _termination_message(category: str, detail: str | None) -> str:
    label = TERMINATION_CATEGORY_LABELS[category]
    return f"Motivo: {label}. {detail}" if detail else f"Motivo: {label}."


def terminate_student(
    db: Session, user: User, student_id: str, data: StudentTerminationRequest, today: date
) -> StudentTerminationResult:
    """Escenarios 1 y 2: da de baja la suscripción del alumno con el motivo indicado."""
    trainer = _trainer_profile(db, user)
    # 404 si no hay vínculo activo (incluye una baja repetida o un alumno de otro entrenador).
    relationship = _active_relationship(db, trainer.id, student_id)

    now = datetime.now(UTC).replace(tzinfo=None)
    relationship.status = "TERMINATED"
    relationship.end_date = today
    relationship.terminated_at = now
    relationship.termination_category = data.category
    relationship.termination_reason = data.detail

    names = parties(db, relationship)
    create_notification(
        db,
        recipient_id=names.student_user_id,
        type=SUBSCRIPTION_TERMINATED,
        title=preview(f"Tu entrenador {names.trainer_name} finalizó tu suscripción", 150),
        message=_termination_message(data.category, data.detail),
        related_entity_type="TrainingRelationship",
        related_entity_id=relationship.id,
        related_student_id=relationship.student_id,
    )
    db.commit()
    db.refresh(relationship)

    return StudentTerminationResult(
        relationship_id=relationship.id,
        student_id=relationship.student_id,
        status="TERMINATED",
        end_date=relationship.end_date,
        terminated_at=relationship.terminated_at,
        category=data.category,
        detail=data.detail,
        available_slots=int(quota_summary(db, trainer)["available_slots"]),
    )
