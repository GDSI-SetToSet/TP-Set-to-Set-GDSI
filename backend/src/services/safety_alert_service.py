"""Servicio de dominio para alertas de seguridad (US-29)."""

from datetime import datetime

from fastapi import status
from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE, canonical_zone_key
from backend.src.models.body_map_report import BodyMapPainReport, BodyMapPainReportZone
from backend.src.models.exercise import Exercise
from backend.src.models.safety_alert import SafetyAlert
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.body_map_report import (
    CANONICAL_ZONE_BY_KEY,
    ZONE_DISPLAY_NAMES,
)
from backend.src.schemas.safety_alert import (
    SafetyAlertReviewRequest,
    SafetyAlertStatus,
    SafetyAlertView,
    StudentPainAlertReviewedNotice,
)
from backend.src.services.notification_service import create_notification
from backend.src.services.trainer_service import utc_now

REPEATED_DISCOMFORT_NOTIFICATION = "REPEATED_DISCOMFORT_ALERT"
EXCESSIVE_EFFORT_NOTIFICATION = "EXCESSIVE_EFFORT_ALERT"

ACTION_DISPLAY_LABELS: dict[str, str] = {
    "ADJUSTED_ROUTINE": "Ajusté la rutina",
    "CONTACTED_STUDENT": "Contacté al alumno",
    "NO_ACTION": "Sin acción",
}


class SafetyAlertError(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        errors: list[dict[str, str]] | None = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def _require_role(user: User, expected_role: str) -> None:
    if user.role != expected_role:
        role_label = "entrenadores" if expected_role == TRAINER_ROLE else "alumnos"
        raise SafetyAlertError(
            status.HTTP_403_FORBIDDEN,
            f"Esta acción está disponible solo para {role_label}.",
        )


def _get_trainer_profile(db: Session, user: User) -> TrainerProfile:
    _require_role(user, TRAINER_ROLE)
    trainer = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == user.id))
    if trainer is None:
        raise SafetyAlertError(status.HTTP_404_NOT_FOUND, "No encontramos tu perfil de entrenador.")
    return trainer


def _get_student_profile(db: Session, user: User) -> StudentProfile:
    _require_role(user, STUDENT_ROLE)
    student = db.scalar(
        select(StudentProfile)
        .where(StudentProfile.user_id == user.id)
        .options(selectinload(StudentProfile.user))
    )
    if student is None:
        raise SafetyAlertError(status.HTTP_404_NOT_FOUND, "No encontramos tu perfil de alumno.")
    return student


def _format_student_name(student: StudentProfile, user: User | None = None) -> str:
    full_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
    if full_name:
        return full_name
    if user is not None and user.email:
        return user.email
    if getattr(student, "user", None) is not None and student.user.email:
        return student.user.email
    return "Alumno"


def _canonical_zone_name(zone: str | None) -> str | None:
    if not zone:
        return None
    key = canonical_zone_key(zone)
    return CANONICAL_ZONE_BY_KEY.get(key, zone)


def _zone_display_name(zone: str | None) -> str | None:
    if not zone:
        return None
    canonical = _canonical_zone_name(zone) or zone
    return ZONE_DISPLAY_NAMES.get(canonical, canonical)


def _serialize_alert(alert: SafetyAlert) -> SafetyAlertView:
    student_name = _format_student_name(alert.student)
    return SafetyAlertView(
        id=alert.id,
        relationship_id=alert.relationship_id,
        student_id=alert.student_id,
        student_name=student_name,
        session_id=alert.session_id,
        session_day_name=alert.session.day_name if alert.session else None,
        report_id=alert.report_id,
        exercise_id=alert.exercise_id,
        exercise_name=alert.exercise.name if alert.exercise else None,
        alert_type=alert.alert_type,
        zone=alert.zone,
        zone_display_name=_zone_display_name(alert.zone),
        rpe=alert.rpe,
        status=alert.status,
        action_taken=alert.action_taken,
        trainer_note=alert.trainer_note,
        created_at=alert.created_at,
        reviewed_at=alert.reviewed_at,
        student_seen_at=alert.student_seen_at,
    )


def _serialize_reviewed_pain_notice(alert: SafetyAlert) -> StudentPainAlertReviewedNotice:
    assert alert.action_taken is not None and alert.reviewed_at is not None
    return StudentPainAlertReviewedNotice(
        id=alert.id,
        session_id=alert.session_id,
        session_day_name=alert.session.day_name if alert.session else None,
        exercise_name=alert.exercise.name if alert.exercise else None,
        zone=alert.zone,
        zone_display_name=_zone_display_name(alert.zone),
        action_taken=alert.action_taken,
        trainer_note=alert.trainer_note,
        reviewed_at=alert.reviewed_at,
    )


def _create_alert_idempotent(
    db: Session,
    *,
    relationship_id: str,
    trainer_id: str,
    student_id: str,
    session_id: str | None,
    report_id: str | None,
    exercise_id: str | None,
    alert_type: str,
    zone: str | None,
    rpe: int | None,
    dedup_key: str,
    created_at: datetime,
) -> tuple[SafetyAlert, bool]:
    existing = db.scalar(select(SafetyAlert).where(SafetyAlert.dedup_key == dedup_key))
    if existing is not None:
        return existing, False

    alert = SafetyAlert(
        relationship_id=relationship_id,
        trainer_id=trainer_id,
        student_id=student_id,
        session_id=session_id,
        report_id=report_id,
        exercise_id=exercise_id,
        alert_type=alert_type,
        zone=zone,
        rpe=rpe,
        dedup_key=dedup_key,
        status="PENDING",
        created_at=created_at,
    )
    try:
        with db.begin_nested():
            db.add(alert)
            db.flush()
        return alert, True
    except IntegrityError:
        existing = db.scalar(select(SafetyAlert).where(SafetyAlert.dedup_key == dedup_key))
        if existing is not None:
            return existing, False
        raise


def _base_alert_load_options():
    return (
        selectinload(SafetyAlert.relationship),
        selectinload(SafetyAlert.student).selectinload(StudentProfile.user),
        selectinload(SafetyAlert.session),
        selectinload(SafetyAlert.exercise),
    )


def create_pain_alerts_for_report(
    db: Session,
    *,
    report: BodyMapPainReport,
    relationship: TrainingRelationship | None,
    student: StudentProfile,
    session: WorkoutSession | None,
    exercise: Exercise | None,
    now: datetime,
) -> list[SafetyAlert]:
    """CA-1: crea una SafetyAlert(PAIN) por cada zona con dolor del reporte en relación activa."""
    if (
        relationship is None
        or relationship.status != "ACTIVE"
        or relationship.trainer is None
        or report.relationship_id != relationship.id
    ):
        return []

    created_or_existing: list[SafetyAlert] = []
    exercise_id = exercise.id if (report.context == "IN_EXERCISE" and exercise is not None) else None
    for zone_record in report.zones:
        if zone_record.intensity != "PAIN":
            continue
        canonical_zone = _canonical_zone_name(zone_record.zone) or zone_record.zone
        dedup_key = f"PAIN:{report.id}:{canonical_zone}"
        alert, _ = _create_alert_idempotent(
            db,
            relationship_id=relationship.id,
            trainer_id=relationship.trainer_id,
            student_id=student.id,
            session_id=session.id if session is not None else report.session_id,
            report_id=report.id,
            exercise_id=exercise_id,
            alert_type="PAIN",
            zone=canonical_zone,
            rpe=None,
            dedup_key=dedup_key,
            created_at=now,
        )
        created_or_existing.append(alert)
    return created_or_existing


def _participating_session_has_activity_clause():
    return or_(
        exists(select(WorkoutSetLog.id).where(WorkoutSetLog.session_id == WorkoutSession.id)),
        exists(select(BodyMapPainReport.id).where(BodyMapPainReport.session_id == WorkoutSession.id)),
    )


def _previous_participating_session(
    db: Session,
    *,
    relationship_id: str,
    current_session: WorkoutSession,
) -> WorkoutSession | None:
    """CA-2: sesión participante inmediatamente anterior en orden (started_at DESC, id DESC).

    Participa e interrumpe únicamente una sesión con `started_at IS NOT NULL` y actividad registrada
    (`WorkoutSetLog` o `BodyMapPainReport`), sin importar si fue finalizada (`finished_at IS NULL` cuenta).
    """
    if current_session.started_at is None:
        return None

    return db.scalar(
        select(WorkoutSession)
        .where(
            WorkoutSession.relationship_id == relationship_id,
            WorkoutSession.started_at.is_not(None),
            or_(
                WorkoutSession.started_at < current_session.started_at,
                and_(
                    WorkoutSession.started_at == current_session.started_at,
                    WorkoutSession.id < current_session.id,
                ),
            ),
            _participating_session_has_activity_clause(),
        )
        .order_by(WorkoutSession.started_at.desc(), WorkoutSession.id.desc())
        .limit(1)
    )


def _next_participating_session(
    db: Session,
    *,
    relationship_id: str,
    current_session: WorkoutSession,
) -> WorkoutSession | None:
    """CA-2 (LOW-04): sesión participante inmediatamente posterior en orden (started_at ASC, id ASC)."""
    if current_session.started_at is None:
        return None

    return db.scalar(
        select(WorkoutSession)
        .where(
            WorkoutSession.relationship_id == relationship_id,
            WorkoutSession.id != current_session.id,
            WorkoutSession.started_at.is_not(None),
            or_(
                WorkoutSession.started_at > current_session.started_at,
                and_(
                    WorkoutSession.started_at == current_session.started_at,
                    WorkoutSession.id > current_session.id,
                ),
            ),
            _participating_session_has_activity_clause(),
        )
        .order_by(WorkoutSession.started_at.asc(), WorkoutSession.id.asc())
        .limit(1)
    )


def _latest_discomfort_reports_by_zone(
    db: Session,
    *,
    session_id: str,
    relationship_id: str,
) -> dict[str, BodyMapPainReport]:
    """Devuelve el último BodyMapPainReport con DISCOMFORT por canonical_zone_key en la sesión."""
    rows = db.execute(
        select(BodyMapPainReportZone.zone, BodyMapPainReport)
        .join(BodyMapPainReport, BodyMapPainReportZone.report_id == BodyMapPainReport.id)
        .where(
            BodyMapPainReport.session_id == session_id,
            BodyMapPainReport.relationship_id == relationship_id,
            BodyMapPainReportZone.intensity == "DISCOMFORT",
        )
        .options(selectinload(BodyMapPainReport.exercise))
        .order_by(BodyMapPainReport.created_at.desc(), BodyMapPainReport.id.desc())
    ).all()

    by_zone: dict[str, BodyMapPainReport] = {}
    for zone_name, report in rows:
        if not zone_name:
            continue
        z_key = canonical_zone_key(zone_name)
        if z_key not in by_zone:
            by_zone[z_key] = report
    return by_zone


def _emit_repeated_discomfort_for_pair(
    db: Session,
    *,
    earlier_session: WorkoutSession,
    later_session: WorkoutSession,
    candidate_zones: list[str],
    relationship: TrainingRelationship,
    student: StudentProfile,
    student_user: User,
    preferred_report: BodyMapPainReport | None,
    preferred_exercise: Exercise | None,
    now: datetime,
) -> list[SafetyAlert]:
    earlier_discomfort_by_zone = _latest_discomfort_reports_by_zone(
        db,
        session_id=earlier_session.id,
        relationship_id=relationship.id,
    )
    if not earlier_discomfort_by_zone:
        return []

    later_discomfort_by_zone = _latest_discomfort_reports_by_zone(
        db,
        session_id=later_session.id,
        relationship_id=relationship.id,
    )
    if not later_discomfort_by_zone:
        return []

    student_name = _format_student_name(student, student_user)
    alerts: list[SafetyAlert] = []
    for canonical_zone in candidate_zones:
        z_key = canonical_zone_key(canonical_zone)
        if z_key not in earlier_discomfort_by_zone or z_key not in later_discomfort_by_zone:
            continue

        if preferred_report is not None and preferred_report.session_id == later_session.id:
            target_report = preferred_report
            target_exercise = preferred_exercise
        else:
            target_report = later_discomfort_by_zone[z_key]
            target_exercise = target_report.exercise

        target_exercise_id = (
            target_exercise.id
            if (target_report.context == "IN_EXERCISE" and target_exercise is not None)
            else None
        )
        dedup_key = f"REPEATED_DISCOMFORT:{relationship.id}:{later_session.id}:{canonical_zone}"
        alert, created = _create_alert_idempotent(
            db,
            relationship_id=relationship.id,
            trainer_id=relationship.trainer_id,
            student_id=student.id,
            session_id=later_session.id,
            report_id=target_report.id,
            exercise_id=target_exercise_id,
            alert_type="REPEATED_DISCOMFORT",
            zone=canonical_zone,
            rpe=None,
            dedup_key=dedup_key,
            created_at=now,
        )
        alerts.append(alert)
        if created:
            context_details: list[str] = []
            if target_exercise is not None and target_report.context == "IN_EXERCISE":
                context_details.append(f'en el ejercicio "{target_exercise.name}"')
            context_details.append(f'durante "{later_session.day_name}"')
            detail_text = f" ({' '.join(context_details)})"
            zone_display = _zone_display_name(canonical_zone) or canonical_zone
            create_notification(
                db,
                recipient_id=relationship.trainer.user_id,
                type=REPEATED_DISCOMFORT_NOTIFICATION,
                title="Alerta de molestia repetida",
                message=(
                    f"{student_name} reportó molestia repetida en {zone_display} "
                    f"durante 2 sesiones consecutivas{detail_text}. "
                    "Revisá la alerta de seguridad."
                ),
                related_entity_type="SAFETY_ALERT",
                related_entity_id=alert.id,
                related_student_id=student.id,
                related_session_id=later_session.id,
                commit=False,
            )
    return alerts


def evaluate_repeated_discomfort_alerts(
    db: Session,
    *,
    report: BodyMapPainReport,
    relationship: TrainingRelationship | None,
    student: StudentProfile,
    student_user: User,
    session: WorkoutSession | None,
    exercise: Exercise | None,
    now: datetime,
) -> list[SafetyAlert]:
    """CA-2: detecta molestia (DISCOMFORT) en la misma zona en 2 sesiones participantes consecutivas."""
    if report.session_id is None or session is None or session.started_at is None:
        return []
    if (
        relationship is None
        or relationship.status != "ACTIVE"
        or relationship.trainer is None
        or report.relationship_id != relationship.id
        or session.relationship_id != relationship.id
    ):
        return []

    discomfort_zones: list[str] = []
    seen_zone_keys: set[str] = set()
    for zone_record in report.zones:
        if zone_record.intensity != "DISCOMFORT":
            continue
        canonical_zone = _canonical_zone_name(zone_record.zone) or zone_record.zone
        z_key = canonical_zone_key(canonical_zone)
        if z_key not in seen_zone_keys:
            seen_zone_keys.add(z_key)
            discomfort_zones.append(canonical_zone)

    if not discomfort_zones:
        return []

    alerts: list[SafetyAlert] = []
    prev_session = _previous_participating_session(
        db,
        relationship_id=relationship.id,
        current_session=session,
    )
    if prev_session is not None:
        alerts.extend(
            _emit_repeated_discomfort_for_pair(
                db,
                earlier_session=prev_session,
                later_session=session,
                candidate_zones=discomfort_zones,
                relationship=relationship,
                student=student,
                student_user=student_user,
                preferred_report=report,
                preferred_exercise=exercise,
                now=now,
            )
        )

    # CA-2 (LOW-04): si se reporta tardíamente sobre una sesión anterior, también evaluar (session, next_session).
    next_session = _next_participating_session(
        db,
        relationship_id=relationship.id,
        current_session=session,
    )
    if next_session is not None:
        alerts.extend(
            _emit_repeated_discomfort_for_pair(
                db,
                earlier_session=session,
                later_session=next_session,
                candidate_zones=discomfort_zones,
                relationship=relationship,
                student=student,
                student_user=student_user,
                preferred_report=report,
                preferred_exercise=exercise,
                now=now,
            )
        )

    return alerts


def create_excessive_effort_alert(
    db: Session,
    session: WorkoutSession,
    *,
    now: datetime | None = None,
) -> SafetyAlert | None:
    """CA-3: emite SafetyAlert(EXCESSIVE_EFFORT) y notificación al persistirse RPE 9 o 10."""
    if session.rpe not in (9, 10):
        return None

    relationship = db.scalar(
        select(TrainingRelationship)
        .where(
            TrainingRelationship.id == session.relationship_id,
            TrainingRelationship.status == "ACTIVE",
        )
        .options(
            selectinload(TrainingRelationship.trainer),
            selectinload(TrainingRelationship.student).selectinload(StudentProfile.user),
        )
    )
    if (
        relationship is None
        or relationship.trainer is None
        or relationship.student is None
    ):
        return None

    created_at = now or utc_now()
    dedup_key = f"EXCESSIVE_EFFORT:{session.id}"
    alert, created = _create_alert_idempotent(
        db,
        relationship_id=relationship.id,
        trainer_id=relationship.trainer_id,
        student_id=relationship.student_id,
        session_id=session.id,
        report_id=None,
        exercise_id=None,
        alert_type="EXCESSIVE_EFFORT",
        zone=None,
        rpe=session.rpe,
        dedup_key=dedup_key,
        created_at=created_at,
    )
    if created:
        student_name = _format_student_name(relationship.student)
        create_notification(
            db,
            recipient_id=relationship.trainer.user_id,
            type=EXCESSIVE_EFFORT_NOTIFICATION,
            title="Alerta de esfuerzo excesivo",
            message=(
                f'{student_name} reportó un esfuerzo excesivo (RPE {session.rpe}/10) '
                f'en "{session.day_name}". Revisá la alerta de seguridad.'
            ),
            related_entity_type="SAFETY_ALERT",
            related_entity_id=alert.id,
            related_student_id=relationship.student_id,
            related_session_id=session.id,
            commit=False,
        )
    return alert


def list_trainer_safety_alerts(
    db: Session,
    user: User,
    *,
    status_filter: SafetyAlertStatus | None = None,
    student_id: str | None = None,
) -> list[SafetyAlertView]:
    trainer = _get_trainer_profile(db, user)
    stmt = (
        select(SafetyAlert)
        .join(TrainingRelationship, SafetyAlert.relationship_id == TrainingRelationship.id)
        .where(
            SafetyAlert.trainer_id == trainer.id,
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
        .options(*_base_alert_load_options())
    )
    if status_filter is not None:
        stmt = stmt.where(SafetyAlert.status == status_filter)
    if student_id is not None:
        stmt = stmt.where(SafetyAlert.student_id == student_id)

    stmt = stmt.order_by(
        case((SafetyAlert.status == "PENDING", 0), else_=1),
        SafetyAlert.created_at.desc(),
        SafetyAlert.id.desc(),
    )
    alerts = db.scalars(stmt).all()
    return [_serialize_alert(alert) for alert in alerts]


def list_trainer_student_safety_alerts(
    db: Session,
    user: User,
    student_id: str,
    *,
    status_filter: SafetyAlertStatus | None = None,
) -> list[SafetyAlertView]:
    trainer = _get_trainer_profile(db, user)
    active_rel = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.student_id == student_id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if active_rel is None:
        raise SafetyAlertError(
            status.HTTP_404_NOT_FOUND,
            "No encontramos un alumno activo con ese identificador.",
        )

    stmt = (
        select(SafetyAlert)
        .where(
            SafetyAlert.relationship_id == active_rel.id,
            SafetyAlert.trainer_id == trainer.id,
            SafetyAlert.student_id == student_id,
        )
        .options(*_base_alert_load_options())
    )
    if status_filter is not None:
        stmt = stmt.where(SafetyAlert.status == status_filter)

    stmt = stmt.order_by(
        case((SafetyAlert.status == "PENDING", 0), else_=1),
        SafetyAlert.created_at.desc(),
        SafetyAlert.id.desc(),
    )
    alerts = db.scalars(stmt).all()
    return [_serialize_alert(alert) for alert in alerts]


def review_safety_alert(
    db: Session,
    user: User,
    alert_id: str,
    payload: SafetyAlertReviewRequest,
) -> SafetyAlertView:
    trainer = _get_trainer_profile(db, user)
    alert = db.scalar(
        select(SafetyAlert)
        .where(SafetyAlert.id == alert_id)
        .options(*_base_alert_load_options())
    )
    if (
        alert is None
        or alert.trainer_id != trainer.id
        or alert.relationship is None
        or alert.relationship.trainer_id != trainer.id
        or alert.relationship.status != "ACTIVE"
    ):
        raise SafetyAlertError(
            status.HTTP_404_NOT_FOUND,
            "No encontramos esa alerta de seguridad.",
        )

    if alert.status == "REVIEWED":
        raise SafetyAlertError(
            status.HTTP_409_CONFLICT,
            "Esta alerta de seguridad ya fue marcada como revisada.",
        )

    alert.status = "REVIEWED"
    alert.action_taken = payload.action_taken
    alert.trainer_note = payload.trainer_note
    alert.reviewed_at = utc_now()
    db.commit()
    db.refresh(alert)
    return _serialize_alert(alert)


def list_student_reviewed_pain_notices(
    db: Session,
    user: User,
) -> list[StudentPainAlertReviewedNotice]:
    """CA-5: solo alertas PAIN, estado REVIEWED, aún no vistas, del vínculo ACTIVE del alumno."""
    student = _get_student_profile(db, user)
    alerts = db.scalars(
        select(SafetyAlert)
        .join(TrainingRelationship, SafetyAlert.relationship_id == TrainingRelationship.id)
        .where(
            SafetyAlert.student_id == student.id,
            TrainingRelationship.student_id == student.id,
            TrainingRelationship.status == "ACTIVE",
            SafetyAlert.alert_type == "PAIN",
            SafetyAlert.status == "REVIEWED",
            SafetyAlert.action_taken.is_not(None),
            SafetyAlert.reviewed_at.is_not(None),
            SafetyAlert.student_seen_at.is_(None),
        )
        .options(
            selectinload(SafetyAlert.session),
            selectinload(SafetyAlert.exercise),
        )
        .order_by(SafetyAlert.reviewed_at.asc(), SafetyAlert.created_at.asc())
    ).all()
    return [_serialize_reviewed_pain_notice(alert) for alert in alerts]


def mark_safety_alert_seen(
    db: Session,
    user: User,
    alert_id: str,
) -> StudentPainAlertReviewedNotice:
    """CA-5: marca consumo único (student_seen_at) solo para alertas PAIN revisadas del alumno activo."""
    student = _get_student_profile(db, user)
    alert = db.scalar(
        select(SafetyAlert)
        .where(SafetyAlert.id == alert_id)
        .options(
            selectinload(SafetyAlert.relationship),
            selectinload(SafetyAlert.session),
            selectinload(SafetyAlert.exercise),
        )
    )
    if (
        alert is None
        or alert.student_id != student.id
        or alert.relationship is None
        or alert.relationship.student_id != student.id
        or alert.relationship.status != "ACTIVE"
        or alert.alert_type != "PAIN"
    ):
        raise SafetyAlertError(
            status.HTTP_404_NOT_FOUND,
            "No encontramos ese aviso de seguridad.",
        )

    if alert.status != "REVIEWED" or alert.action_taken is None or alert.reviewed_at is None:
        raise SafetyAlertError(
            status.HTTP_404_NOT_FOUND,
            "Ese reporte de dolor todavía no fue revisado por tu entrenador.",
        )

    if alert.student_seen_at is None:
        alert.student_seen_at = utc_now()
        db.commit()
        db.refresh(alert)

    return _serialize_reviewed_pain_notice(alert)


def unreviewed_alert_summary_by_relationship(
    db: Session,
    relationship_ids: list[str],
) -> dict[str, tuple[int, datetime | None]]:
    """Retorna {relationship_id: (pending_count, latest_created_at)} solo sobre vínculos ACTIVE."""
    if not relationship_ids:
        return {}
    rows = db.execute(
        select(
            SafetyAlert.relationship_id,
            func.count(SafetyAlert.id),
            func.max(SafetyAlert.created_at),
        )
        .join(TrainingRelationship, SafetyAlert.relationship_id == TrainingRelationship.id)
        .where(
            SafetyAlert.relationship_id.in_(relationship_ids),
            TrainingRelationship.status == "ACTIVE",
            SafetyAlert.status == "PENDING",
        )
        .group_by(SafetyAlert.relationship_id)
    ).all()
    return {
        rel_id: (int(count or 0), latest_created_at)
        for rel_id, count, latest_created_at in rows
    }


def student_safety_indicators(db: Session, relationship_id: str) -> list[str]:
    """Genera indicadores legibles de alertas PENDING del vínculo activo para US-18 detalle."""
    alerts = db.scalars(
        select(SafetyAlert)
        .join(TrainingRelationship, SafetyAlert.relationship_id == TrainingRelationship.id)
        .where(
            SafetyAlert.relationship_id == relationship_id,
            TrainingRelationship.status == "ACTIVE",
            SafetyAlert.status == "PENDING",
        )
        .options(selectinload(SafetyAlert.exercise))
        .order_by(SafetyAlert.created_at.desc(), SafetyAlert.id.desc())
    ).all()

    indicators: list[str] = []
    for alert in alerts:
        if alert.alert_type == "PAIN":
            zone_label = _zone_display_name(alert.zone) or "zona reportada"
            suffix = f" ({alert.exercise.name})" if alert.exercise is not None else ""
            indicators.append(f"Dolor sin revisar en {zone_label}{suffix}")
        elif alert.alert_type == "REPEATED_DISCOMFORT":
            zone_label = _zone_display_name(alert.zone) or "zona reportada"
            suffix = f" ({alert.exercise.name})" if alert.exercise is not None else ""
            indicators.append(f"Molestia repetida sin revisar en {zone_label}{suffix}")
        elif alert.alert_type == "EXCESSIVE_EFFORT":
            indicators.append(f"Esfuerzo excesivo sin revisar (RPE {alert.rpe}/10)")
    return indicators
