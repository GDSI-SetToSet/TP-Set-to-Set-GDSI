from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE, canonical_zone_key
from backend.src.models.assigned_routine import (
    AssignedRoutineBlock,
    AssignedRoutineDay,
    AssignedRoutineExercise,
)
from backend.src.models.body_map_report import BodyMapPainReport, BodyMapPainReportZone
from backend.src.models.exercise import Exercise
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.body_map_report import (
    ZONE_DISPLAY_NAMES,
    BodyMapReportCreate,
    BodyMapReportResponse,
    BodyMapZoneHistoryItem,
    ReportZoneOutput,
    SafeVariantEvaluation,
    SafeVariantSnippet,
)
from backend.src.services.notification_service import create_notification
from backend.src.services.safe_variant_service import (
    NO_VARIANT_MESSAGE,
    resolve_variant,
    student_zones,
)
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.trainer_service import (
    get_or_create_profile as get_trainer_profile,
)


class BodyMapReportError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_student(user: User) -> None:
    if user.role != STUDENT_ROLE:
        raise BodyMapReportError(
            status.HTTP_403_FORBIDDEN,
            "Esta acción está reservada exclusivamente para alumnos.",
        )


def _require_trainer(user: User) -> None:
    if user.role != TRAINER_ROLE:
        raise BodyMapReportError(
            status.HTTP_403_FORBIDDEN,
            "Esta acción está reservada exclusivamente para entrenadores.",
        )


def _get_active_relationship(db: Session, student_id: str) -> TrainingRelationship | None:
    return db.scalar(
        select(TrainingRelationship)
        .where(
            TrainingRelationship.student_id == student_id,
            TrainingRelationship.status == "ACTIVE",
        )
        .order_by(TrainingRelationship.start_date.desc())
    )


def _evaluate_safe_variant_for_report(
    db: Session, student_id: str, exercise: Exercise, zones_payload: list[Any]
) -> SafeVariantEvaluation:
    # Combinamos las zonas reportadas con dolor o molestia más las restricciones permanentes
    reported_keys = {
        canonical_zone_key(z.zone)
        for z in zones_payload
        if canonical_zone_key(z.zone) and z.intensity in ("PAIN", "DISCOMFORT")
    }
    # Si ninguna fue molestia/dolor pero se pide variante, consideramos todas las reportadas
    if not reported_keys:
        reported_keys = {canonical_zone_key(z.zone) for z in zones_payload if canonical_zone_key(z.zone)}

    combined_zones = reported_keys | student_zones(db, student_id)
    res_status, variant = resolve_variant(db, exercise, combined_zones)

    if res_status == "VARIANT" and variant is not None:
        video_platform_val = (
            variant.video_platform.value
            if hasattr(variant.video_platform, "value")
            else str(variant.video_platform)
            if variant.video_platform
            else None
        )
        return SafeVariantEvaluation(
            status="VARIANT",
            variant=SafeVariantSnippet(
                exercise_id=variant.id,
                name=variant.name,
                description=variant.description,
                video_url=variant.video_url,
                video_platform=video_platform_val,
            ),
            message=None,
            can_skip=False,
        )
    if res_status == "BLOCKED":
        return SafeVariantEvaluation(
            status="BLOCKED",
            variant=None,
            message=NO_VARIANT_MESSAGE,
            can_skip=True,
        )
    return SafeVariantEvaluation(
        status="SAFE",
        variant=None,
        message=None,
        can_skip=False,
    )


def _build_report_response(
    report: BodyMapPainReport,
    exercise_name: str | None = None,
    safe_variant: SafeVariantEvaluation | None = None,
) -> BodyMapReportResponse:
    zones_out = [
        ReportZoneOutput(
            id=z.id,
            zone=z.zone,
            zone_display=ZONE_DISPLAY_NAMES.get(z.zone, z.zone),
            intensity=z.intensity,  # type: ignore[arg-type]
            created_at=z.created_at,
        )
        for z in report.zones
    ]
    return BodyMapReportResponse(
        id=report.id,
        student_id=report.student_id,
        session_id=report.session_id,
        exercise_id=report.exercise_id,
        exercise_name=exercise_name or (report.exercise.name if report.exercise else None),
        context=report.context,
        action_taken=report.action_taken,
        created_at=report.created_at,
        zones=zones_out,
        safe_variant=safe_variant,
    )


def _is_equivalent_payload(existing: BodyMapPainReport, payload: BodyMapReportCreate) -> bool:
    if existing.context != payload.context:
        return False
    if (existing.session_id or None) != (payload.session_id or None):
        return False
    if (existing.exercise_id or None) != (payload.exercise_id or None):
        return False
    existing_zones = sorted((z.zone, z.intensity) for z in existing.zones)
    payload_zones = sorted((z.zone, z.intensity) for z in payload.zones)
    return existing_zones == payload_zones


def create_body_map_report(
    db: Session, user: User, payload: BodyMapReportCreate
) -> BodyMapReportResponse:
    _require_student(user)
    profile = get_student_profile(db, user)

    # 1. Deduplicación por idempotency_key (H03)
    if payload.idempotency_key:
        existing = db.scalar(
            select(BodyMapPainReport)
            .where(
                BodyMapPainReport.idempotency_key == payload.idempotency_key,
                BodyMapPainReport.student_id == profile.id,
            )
            .options(selectinload(BodyMapPainReport.zones), selectinload(BodyMapPainReport.exercise))
        )
        if existing:
            if not _is_equivalent_payload(existing, payload):
                raise BodyMapReportError(
                    status.HTTP_409_CONFLICT,
                    "La clave de idempotencia ya fue utilizada con un contenido de reporte diferente.",
                )
            safe_var = None
            if existing.exercise:
                safe_var = _evaluate_safe_variant_for_report(
                    db, profile.id, existing.exercise, payload.zones
                )
            return _build_report_response(existing, safe_variant=safe_var)

    # 2. Validación de coherencia y pertenencia de contexto, sesión y ejercicio (H04)
    if payload.context == "POST_SESSION" and payload.exercise_id is not None:
        raise BodyMapReportError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Un reporte al finalizar la sesión (POST_SESSION) es general y no debe incluir un identificador de ejercicio.",
        )

    if payload.context == "IN_EXERCISE":
        if not payload.exercise_id:
            raise BodyMapReportError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Para un reporte durante el ejercicio se debe especificar el identificador del ejercicio.",
            )
        if not payload.session_id:
            raise BodyMapReportError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Para un reporte durante el ejercicio se debe especificar la sesión de entrenamiento activa.",
            )

    session = None
    if payload.session_id:
        session = db.scalar(
            select(WorkoutSession).where(
                WorkoutSession.id == payload.session_id,
                WorkoutSession.student_id == profile.id,
            )
        )
        if session is None:
            raise BodyMapReportError(
                status.HTTP_404_NOT_FOUND,
                "La sesión de entrenamiento indicada no existe o no pertenece a tu perfil.",
            )

    exercise = None
    if payload.exercise_id:
        exercise = db.get(Exercise, payload.exercise_id)
        if exercise is None:
            raise BodyMapReportError(
                status.HTTP_404_NOT_FOUND,
                "El ejercicio indicado no fue encontrado en el sistema.",
            )

    # Validación de pertenencia del ejercicio a la sesión asignada o ejecutada (H04)
    if payload.context == "IN_EXERCISE" and session and exercise:
        is_in_routine_day = db.scalar(
            select(AssignedRoutineExercise.id)
            .join(AssignedRoutineBlock, AssignedRoutineExercise.block_id == AssignedRoutineBlock.id)
            .join(AssignedRoutineDay, AssignedRoutineBlock.day_id == AssignedRoutineDay.id)
            .where(
                AssignedRoutineDay.routine_id == session.routine_id,
                AssignedRoutineDay.name == session.day_name,
                AssignedRoutineExercise.exercise_id == payload.exercise_id,
            )
            .limit(1)
        ) is not None

        is_in_session_logs = db.scalar(
            select(WorkoutSetLog.id)
            .where(
                WorkoutSetLog.session_id == session.id,
                WorkoutSetLog.exercise_id == payload.exercise_id,
            )
            .limit(1)
        ) is not None

        if not (is_in_routine_day or is_in_session_logs):
            raise BodyMapReportError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f'El ejercicio "{exercise.name}" no forma parte del entrenamiento programado ni ejecutado en esta sesión.',
            )

    # 3. Deduplicación natural ante reintentos accidentales (mismo alumno, sesión, ejercicio, contexto en ventana de 10 seg)
    now = utc_now()
    window_start = now - timedelta(seconds=10)
    recent_candidates = db.scalars(
        select(BodyMapPainReport)
        .where(
            BodyMapPainReport.student_id == profile.id,
            BodyMapPainReport.session_id == payload.session_id,
            BodyMapPainReport.exercise_id == payload.exercise_id,
            BodyMapPainReport.context == payload.context,
            BodyMapPainReport.created_at >= window_start,
        )
        .options(selectinload(BodyMapPainReport.zones), selectinload(BodyMapPainReport.exercise))
    ).all()

    for cand in recent_candidates:
        if _is_equivalent_payload(cand, payload):
            safe_var = None
            if exercise:
                safe_var = _evaluate_safe_variant_for_report(db, profile.id, exercise, payload.zones)
            return _build_report_response(cand, safe_variant=safe_var)

    # 4. Determinar relación activa
    relationship = _get_active_relationship(db, profile.id)
    relationship_id = relationship.id if relationship else None

    # 5. Evaluación de variante segura si aplica
    safe_variant_eval = None
    if exercise and payload.context == "IN_EXERCISE":
        safe_variant_eval = _evaluate_safe_variant_for_report(db, profile.id, exercise, payload.zones)
        if not payload.action_taken and safe_variant_eval.status == "VARIANT":
            payload.action_taken = "VARIANT_OFFERED"

    # 6. Crear reporte y zonas con protección de concurrencia e idempotencia (H03)
    try:
        with db.begin_nested():
            report = BodyMapPainReport(
                student_id=profile.id,
                relationship_id=relationship_id,
                session_id=payload.session_id,
                exercise_id=payload.exercise_id,
                context=payload.context,
                action_taken=payload.action_taken or "NONE",
                idempotency_key=payload.idempotency_key,
                created_at=now,
            )
            db.add(report)
            db.flush()

            for zone_input in payload.zones:
                zone_record = BodyMapPainReportZone(
                    report_id=report.id,
                    zone=zone_input.zone,
                    intensity=zone_input.intensity,
                    created_at=now,
                )
                db.add(zone_record)
                report.zones.append(zone_record)

            # 7. Disparo de alerta al entrenador ante dolor (PAIN)
            pain_zones = [z.zone for z in payload.zones if z.intensity == "PAIN"]
            if pain_zones and relationship and relationship.trainer:
                trainer_user_id = relationship.trainer.user_id
                student_name = (
                    f"{profile.first_name or ''} {profile.last_name or ''}".strip() or user.email
                )
                pain_displays = [ZONE_DISPLAY_NAMES.get(z, z) for z in pain_zones]
                pain_str = ", ".join(pain_displays)

                context_details = []
                if exercise:
                    context_details.append(f'en el ejercicio "{exercise.name}"')
                if session:
                    context_details.append(f'durante "{session.day_name}"')
                elif payload.context == "POST_SESSION":
                    context_details.append("al finalizar la sesión")

                detail_text = f" ({' '.join(context_details)})" if context_details else ""
                notification_title = "Alerta de dolor reportado"
                notification_message = (
                    f"{student_name} reportó dolor en: {pain_str}{detail_text}. "
                    "Revisá el estado del alumno y considerá ajustar el plan."
                )

                create_notification(
                    db,
                    recipient_id=trainer_user_id,
                    type="PAIN_ALERT",
                    title=notification_title,
                    message=notification_message,
                    related_entity_type="BODY_MAP_PAIN_REPORT",
                    related_entity_id=report.id,
                    related_student_id=report.student_id,
                    related_session_id=report.session_id,
                    commit=False,
                )
            db.flush()
    except IntegrityError:
        # Recuperar en caso de conflicto por concurrencia bajo la misma clave de idempotencia
        if payload.idempotency_key:
            existing = db.scalar(
                select(BodyMapPainReport)
                .where(
                    BodyMapPainReport.idempotency_key == payload.idempotency_key,
                    BodyMapPainReport.student_id == profile.id,
                )
                .options(selectinload(BodyMapPainReport.zones), selectinload(BodyMapPainReport.exercise))
            )
            if existing:
                if not _is_equivalent_payload(existing, payload):
                    raise BodyMapReportError(
                        status.HTTP_409_CONFLICT,
                        "La clave de idempotencia ya fue utilizada con un contenido de reporte diferente.",
                    )
                safe_var = None
                if existing.exercise:
                    safe_var = _evaluate_safe_variant_for_report(
                        db, profile.id, existing.exercise, payload.zones
                    )
                return _build_report_response(existing, safe_variant=safe_var)
        raise

    db.commit()
    db.refresh(report)
    return _build_report_response(
        report,
        exercise_name=exercise.name if exercise else None,
        safe_variant=safe_variant_eval,
    )


def update_report_action(
    db: Session, user: User, report_id: str, action_taken: str
) -> BodyMapReportResponse:
    _require_student(user)
    profile = get_student_profile(db, user)

    report = db.scalar(
        select(BodyMapPainReport)
        .where(
            BodyMapPainReport.id == report_id,
            BodyMapPainReport.student_id == profile.id,
        )
        .options(selectinload(BodyMapPainReport.zones), selectinload(BodyMapPainReport.exercise))
    )
    if report is None:
        raise BodyMapReportError(status.HTTP_404_NOT_FOUND, "Reporte no encontrado.")

    report.action_taken = action_taken
    db.commit()
    db.refresh(report)

    safe_var = None
    if report.exercise:
        safe_var = _evaluate_safe_variant_for_report(db, profile.id, report.exercise, report.zones)

    return _build_report_response(report, safe_variant=safe_var)


def list_student_body_map_reports(
    db: Session,
    user: User,
    zone: str | None = None,
    intensity: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BodyMapReportResponse]:
    _require_student(user)
    profile = get_student_profile(db, user)

    query = (
        select(BodyMapPainReport)
        .where(BodyMapPainReport.student_id == profile.id)
        .options(selectinload(BodyMapPainReport.zones), selectinload(BodyMapPainReport.exercise))
    )
    if session_id:
        query = query.where(BodyMapPainReport.session_id == session_id)
    if zone or intensity:
        query = query.join(BodyMapPainReport.zones)
        if zone:
            # Buscar coincidencia exacta o por subcadena
            query = query.where(BodyMapPainReportZone.zone.ilike(f"%{zone.strip()}%"))
        if intensity:
            query = query.where(BodyMapPainReportZone.intensity == intensity.strip().upper())
        query = query.distinct()

    query = query.order_by(desc(BodyMapPainReport.created_at)).offset(offset).limit(limit)
    reports = db.scalars(query).all()
    return [_build_report_response(r) for r in reports]


def list_student_zone_history(
    db: Session,
    user: User,
    zone: str | None = None,
    intensity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[BodyMapZoneHistoryItem]:
    _require_student(user)
    profile = get_student_profile(db, user)

    query = (
        select(BodyMapPainReportZone, BodyMapPainReport, Exercise.name, WorkoutSession.day_name)
        .join(BodyMapPainReport, BodyMapPainReportZone.report_id == BodyMapPainReport.id)
        .outerjoin(Exercise, BodyMapPainReport.exercise_id == Exercise.id)
        .outerjoin(WorkoutSession, BodyMapPainReport.session_id == WorkoutSession.id)
        .where(BodyMapPainReport.student_id == profile.id)
    )
    if zone:
        query = query.where(BodyMapPainReportZone.zone.ilike(f"%{zone.strip()}%"))
    if intensity:
        query = query.where(BodyMapPainReportZone.intensity == intensity.strip().upper())

    query = query.order_by(desc(BodyMapPainReportZone.created_at)).offset(offset).limit(limit)
    rows = db.execute(query).all()

    return [
        BodyMapZoneHistoryItem(
            id=zone_record.id,
            report_id=report.id,
            zone=zone_record.zone,
            zone_display=ZONE_DISPLAY_NAMES.get(zone_record.zone, zone_record.zone),
            intensity=zone_record.intensity,  # type: ignore[arg-type]
            created_at=zone_record.created_at,
            session_id=report.session_id,
            session_day_name=session_day_name,
            exercise_id=report.exercise_id,
            exercise_name=exercise_name,
            context=report.context,
            action_taken=report.action_taken,
        )
        for zone_record, report, exercise_name, session_day_name in rows
    ]


def list_trainer_student_body_map_reports(
    db: Session,
    trainer_user: User,
    student_id: str,
    zone: str | None = None,
    intensity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BodyMapReportResponse]:
    _require_trainer(trainer_user)
    trainer = get_trainer_profile(db, trainer_user)

    rel = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.student_id == student_id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if rel is None:
        raise BodyMapReportError(
            status.HTTP_403_FORBIDDEN,
            "No tenés una relación activa autorizada con este alumno.",
        )

    query = (
        select(BodyMapPainReport)
        .where(BodyMapPainReport.student_id == student_id)
        .options(selectinload(BodyMapPainReport.zones), selectinload(BodyMapPainReport.exercise))
    )
    if zone or intensity:
        query = query.join(BodyMapPainReport.zones)
        if zone:
            query = query.where(BodyMapPainReportZone.zone.ilike(f"%{zone.strip()}%"))
        if intensity:
            query = query.where(BodyMapPainReportZone.intensity == intensity.strip().upper())
        query = query.distinct()

    query = query.order_by(desc(BodyMapPainReport.created_at)).offset(offset).limit(limit)
    reports = db.scalars(query).all()
    return [_build_report_response(r) for r in reports]


def list_trainer_student_zone_history(
    db: Session,
    trainer_user: User,
    student_id: str,
    zone: str | None = None,
    intensity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[BodyMapZoneHistoryItem]:
    _require_trainer(trainer_user)
    trainer = get_trainer_profile(db, trainer_user)

    rel = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.student_id == student_id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if rel is None:
        raise BodyMapReportError(
            status.HTTP_403_FORBIDDEN,
            "No tenés una relación activa autorizada con este alumno.",
        )

    query = (
        select(BodyMapPainReportZone, BodyMapPainReport, Exercise.name, WorkoutSession.day_name)
        .join(BodyMapPainReport, BodyMapPainReportZone.report_id == BodyMapPainReport.id)
        .outerjoin(Exercise, BodyMapPainReport.exercise_id == Exercise.id)
        .outerjoin(WorkoutSession, BodyMapPainReport.session_id == WorkoutSession.id)
        .where(BodyMapPainReport.student_id == student_id)
    )
    if zone:
        query = query.where(BodyMapPainReportZone.zone.ilike(f"%{zone.strip()}%"))
    if intensity:
        query = query.where(BodyMapPainReportZone.intensity == intensity.strip().upper())

    query = query.order_by(desc(BodyMapPainReportZone.created_at)).offset(offset).limit(limit)
    rows = db.execute(query).all()

    return [
        BodyMapZoneHistoryItem(
            id=zone_record.id,
            report_id=report.id,
            zone=zone_record.zone,
            zone_display=ZONE_DISPLAY_NAMES.get(zone_record.zone, zone_record.zone),
            intensity=zone_record.intensity,  # type: ignore[arg-type]
            created_at=zone_record.created_at,
            session_id=report.session_id,
            session_day_name=session_day_name,
            exercise_id=report.exercise_id,
            exercise_name=exercise_name,
            context=report.context,
            action_taken=report.action_taken,
        )
        for zone_record, report, exercise_name, session_day_name in rows
    ]
