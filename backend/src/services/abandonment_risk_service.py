"""US-32: detección de alumnos con riesgo de abandono y alerta al entrenador.

Un alumno está en riesgo cuando no reporta (finaliza) entrenamientos durante 5 entrenamientos
esperados o 2 semanas, lo que ocurra primero. Los entrenamientos esperados se calculan con la
cantidad de días de su rutina por semana. Sin rutina asignada no se esperan entrenamientos.
"""

import math
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.src.models.assigned_routine import AssignedRoutine, AssignedRoutineDay
from backend.src.models.notification import Notification
from backend.src.models.routine_template import RoutineTemplate, RoutineTemplateDay
from backend.src.models.student_profile import StudentProfile
from backend.src.models.student_routine import StudentRoutine
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.schemas.trainer_student import AbandonmentRiskItem
from backend.src.services.notification_service import create_notification
from backend.src.services.trainer_service import (
    TrainerProfileError,
    get_or_create_profile,
)
from backend.src.services.trainer_student_service import TrainerStudentError

MISSED_TRAININGS_THRESHOLD = 5
INACTIVE_DAYS_THRESHOLD = 14
REASON_MISSED_TRAININGS = "MISSED_TRAININGS"
REASON_INACTIVE_TWO_WEEKS = "INACTIVE_TWO_WEEKS"
NOTIFICATION_TYPE = "ABANDONMENT_RISK"


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def evaluate_risk(days_without_report: int, weekly_trainings: int) -> tuple[bool, str | None, int]:
    """Devuelve (en riesgo, motivo, entrenamientos sin reportar)."""
    if weekly_trainings <= 0:
        return False, None, 0
    missed = math.floor(days_without_report * weekly_trainings / 7)
    if missed < MISSED_TRAININGS_THRESHOLD and days_without_report < INACTIVE_DAYS_THRESHOLD:
        return False, None, missed
    # Motivo: el umbral que se alcanza antes según la frecuencia semanal.
    days_to_missed_threshold = math.ceil(MISSED_TRAININGS_THRESHOLD * 7 / weekly_trainings)
    reason = (
        REASON_MISSED_TRAININGS
        if days_to_missed_threshold < INACTIVE_DAYS_THRESHOLD
        else REASON_INACTIVE_TWO_WEEKS
    )
    return True, reason, missed


def _weekly_trainings(db: Session, relationship: TrainingRelationship) -> tuple[int, datetime | None]:
    """Días de rutina por semana y desde cuándo la tiene asignada (si se conoce)."""
    student_routine = db.scalar(
        select(StudentRoutine).where(
            StudentRoutine.relationship_id == relationship.id,
            StudentRoutine.status != "UNASSIGNED",
        )
    )
    if student_routine is not None:
        return len(student_routine.days or []), student_routine.created_at
    if relationship.initial_routine_id:
        template_days = db.scalar(
            select(func.count(RoutineTemplateDay.id))
            .join(RoutineTemplate, RoutineTemplateDay.template_id == RoutineTemplate.id)
            .where(RoutineTemplate.id == relationship.initial_routine_id)
        )
        if template_days:
            return int(template_days), None
        assigned_days = db.scalar(
            select(func.count(AssignedRoutineDay.id))
            .join(AssignedRoutine, AssignedRoutineDay.routine_id == AssignedRoutine.id)
            .where(AssignedRoutine.id == relationship.initial_routine_id, AssignedRoutine.status == "APPROVED")
        )
        return int(assigned_days or 0), None
    return 0, None


def _notify_once(
    db: Session, trainer_user: User, item: AbandonmentRiskItem, since: datetime
) -> bool:
    already_notified = db.scalar(
        select(Notification.id).where(
            Notification.recipient_id == trainer_user.id,
            Notification.type == NOTIFICATION_TYPE,
            Notification.related_entity_id == item.relationship_id,
            Notification.created_at >= since,
        )
    )
    if already_notified:
        return False
    detail = (
        f"lleva {item.missed_trainings} entrenamientos sin reportar"
        if item.reason == REASON_MISSED_TRAININGS
        else f"no reporta entrenamientos hace {item.days_without_report} días"
    )
    create_notification(
        db,
        recipient_id=trainer_user.id,
        type=NOTIFICATION_TYPE,
        title=f"Posible abandono de {item.student_name}",
        message=f"{item.student_name} {detail}. Comunicate para evitar que abandone.",
        related_entity_type="training_relationship",
        related_entity_id=item.relationship_id,
        related_student_id=item.student_id,
    )
    return True


def list_abandonment_risk(
    db: Session, trainer_user: User, now: datetime | None = None, notify: bool = True
) -> list[AbandonmentRiskItem]:
    """Evalúa a los alumnos activos del entrenador; en riesgo primero, y genera la alerta una vez por período."""
    try:
        trainer = get_or_create_profile(db, trainer_user)
    except TrainerProfileError as error:
        raise TrainerStudentError(error.status_code, error.detail) from error
    current = _naive_utc(now) if now else utc_now()

    rows = db.execute(
        select(TrainingRelationship, StudentProfile, User)
        .join(StudentProfile, TrainingRelationship.student_id == StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .where(TrainingRelationship.trainer_id == trainer.id, TrainingRelationship.status == "ACTIVE")
    ).all()
    if not rows:
        return []

    last_reports = dict(
        db.execute(
            select(WorkoutSession.relationship_id, func.max(WorkoutSession.finished_at))
            .where(
                WorkoutSession.relationship_id.in_([relationship.id for relationship, _, _ in rows]),
                WorkoutSession.finished_at.is_not(None),
            )
            .group_by(WorkoutSession.relationship_id)
        ).all()
    )

    items: list[AbandonmentRiskItem] = []
    created = False
    for relationship, student, student_user in rows:
        weekly, routine_since = _weekly_trainings(db, relationship)
        last_report = last_reports.get(relationship.id)
        start = datetime(relationship.start_date.year, relationship.start_date.month, relationship.start_date.day)
        reference = max(
            value for value in (_naive_utc(last_report) if last_report else None, start, routine_since) if value
        )
        days_without_report = max(0, (current - reference).days)
        at_risk, reason, missed = evaluate_risk(days_without_report, weekly)
        name = " ".join(part for part in (student.first_name, student.last_name) if part).strip()
        item = AbandonmentRiskItem(
            relationship_id=relationship.id,
            student_id=student.id,
            student_name=name or student_user.email,
            at_risk=at_risk,
            reason=reason,
            weekly_trainings=weekly,
            days_without_report=days_without_report,
            missed_trainings=missed,
            last_report_at=last_report.replace(tzinfo=UTC) if last_report and last_report.tzinfo is None else last_report,
        )
        if at_risk and notify:
            created = _notify_once(db, trainer_user, item, reference) or created
        items.append(item)

    if created:
        db.commit()
    return sorted(items, key=lambda item: (not item.at_risk, -item.days_without_report, item.student_name))
