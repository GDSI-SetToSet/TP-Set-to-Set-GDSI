"""Devolución del entrenador sobre el esfuerzo reportado (US-64).

Una devolución por sesión con RPE: el entrenador del vínculo activo la crea o
la reemplaza; el alumno de la sesión la lee y la marca como vista. Reglas en
`taskify/specs/008-workout-feedback-and-communication/research.md` (R6, R7).
"""

from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.effort_feedback import EffortFeedback
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.schemas.routine_template import EffortFeedbackInput
from backend.src.services.notification_service import create_notification
from backend.src.services.routine_template_service import (
    VALIDATION_ERROR_STATUS,
    RoutineTemplateError,
    get_student_profile,
    get_trainer_profile,
)
from backend.src.services.trainer_service import utc_now

EFFORT_FEEDBACK_NOTIFICATION = "EFFORT_FEEDBACK"
CATEGORY_LABELS = {
    "MORE_EFFORT": "Podrías exigir más",
    "ADEQUATE": "Esfuerzo adecuado",
    "LESS_INTENSITY": "Bajar la intensidad",
}


def serialize_feedback(feedback: EffortFeedback, session: WorkoutSession) -> dict[str, Any]:
    return {
        "id": feedback.id,
        "session_id": session.id,
        "day_name": session.day_name,
        "session_started_at": session.started_at,
        "rpe": session.rpe,
        "category": feedback.category,
        "comment": feedback.comment,
        "created_at": feedback.created_at,
        "updated_at": feedback.updated_at,
        "seen_at": feedback.seen_at,
    }


def _active_trainer_relationship(db: Session, user: User, relationship_id: str) -> TrainingRelationship:
    trainer = get_trainer_profile(db, user)
    relationship = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.id == relationship_id,
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if relationship is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No se encontró un vínculo activo con ese alumno.")
    return relationship


def upsert_effort_feedback(
    db: Session, user: User, relationship_id: str, session_id: str, payload: EffortFeedbackInput
) -> dict[str, Any]:
    relationship = _active_trainer_relationship(db, user, relationship_id)
    session = db.scalar(
        select(WorkoutSession)
        .where(
            WorkoutSession.id == session_id,
            WorkoutSession.relationship_id == relationship.id,
            WorkoutSession.student_id == relationship.student_id,
        )
        .with_for_update()
    )
    if session is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No encontramos este entrenamiento.")
    if session.finished_at is None or session.rpe is None:
        raise RoutineTemplateError(
            VALIDATION_ERROR_STATUS,
            "Solo podés dejar una devolución sobre un entrenamiento finalizado con esfuerzo reportado.",
        )

    now = utc_now()
    feedback = db.scalar(select(EffortFeedback).where(EffortFeedback.session_id == session.id))
    is_update = feedback is not None
    if feedback is None:
        feedback = EffortFeedback(
            session_id=session.id,
            relationship_id=relationship.id,
            trainer_id=relationship.trainer_id,
            student_id=relationship.student_id,
            created_at=now,
        )
        db.add(feedback)
    feedback.category = payload.category
    feedback.comment = payload.comment
    feedback.updated_at = now
    feedback.seen_at = None
    db.flush()

    student_user_id = relationship.student.user_id if relationship.student else None
    if student_user_id:
        title = "Tu entrenador actualizó su devolución" if is_update else "Tenés una devolución de tu entrenador"
        create_notification(
            db,
            recipient_id=student_user_id,
            type=EFFORT_FEEDBACK_NOTIFICATION,
            title=title,
            message=(
                f"Sobre tu entrenamiento de {session.day_name} (RPE {session.rpe}): "
                f"{CATEGORY_LABELS[feedback.category]}."
            ),
            related_entity_type=EFFORT_FEEDBACK_NOTIFICATION,
            related_entity_id=feedback.id,
            commit=False,
        )

    db.commit()
    db.refresh(feedback)
    return serialize_feedback(feedback, session)


def feedback_by_session(db: Session, session_ids: list[str]) -> dict[str, EffortFeedback]:
    if not session_ids:
        return {}
    rows = db.scalars(select(EffortFeedback).where(EffortFeedback.session_id.in_(session_ids)))
    return {feedback.session_id: feedback for feedback in rows}


def list_student_effort_feedback(db: Session, user: User) -> list[dict[str, Any]]:
    profile = get_student_profile(db, user)
    rows = db.execute(
        select(EffortFeedback, WorkoutSession)
        .join(WorkoutSession, WorkoutSession.id == EffortFeedback.session_id)
        .join(TrainingRelationship, TrainingRelationship.id == EffortFeedback.relationship_id)
        .where(
            EffortFeedback.student_id == profile.id,
            TrainingRelationship.status == "ACTIVE",
        )
        .order_by(EffortFeedback.updated_at.desc(), EffortFeedback.id.desc())
    ).all()
    return [serialize_feedback(feedback, session) for feedback, session in rows]


def mark_effort_feedback_seen(db: Session, user: User, feedback_id: str) -> dict[str, Any]:
    profile = get_student_profile(db, user)
    feedback = db.scalar(
        select(EffortFeedback).where(
            EffortFeedback.id == feedback_id,
            EffortFeedback.student_id == profile.id,
        )
    )
    if feedback is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No encontramos esta devolución.")
    if feedback.seen_at is None:
        feedback.seen_at = utc_now()
        db.commit()
        db.refresh(feedback)
    return serialize_feedback(feedback, feedback.session)
