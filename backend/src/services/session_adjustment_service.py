"""US-26: el entrenador ajusta la próxima sesión de un día de rutina a partir de la sesión finalizada.

El ajuste reescribe ese día en la copia de la rutina del alumno (como una edición confirmada de US-14).
Si el alumno está entrenando, queda pendiente para no alterar la sesión en curso.
"""

from copy import deepcopy

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import (
    BODY_AREAS_ES,
    VALIDATION_ERROR_MESSAGE,
    canonical_zone_key,
)
from backend.src.models.body_map_report import BodyMapPainReport
from backend.src.models.exercise import Exercise
from backend.src.models.exercise_replacement_log import ExerciseReplacementLog
from backend.src.models.session_adjustment import SessionAdjustment
from backend.src.models.student_routine import RoutineChangeLog, StudentRoutine
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.session_adjustment import (
    AdjustmentBlock,
    AdjustmentEntry,
    AdjustmentInput,
    AdjustmentView,
    LoggedExercise,
    LoggedSet,
    ReplacementRequest,
    SessionAdjustmentContext,
    SessionPainZone,
    StudentAdjustmentNotice,
)
from backend.src.services.routine_template_service import RoutineTemplateError
from backend.src.services.student_routine_service import (
    _assignable_source,
    _diff,
    _seed,
    _validate_draft_content,
    ensure_routine,
)
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.trainer_service import (
    get_or_create_profile as get_trainer_profile,
)
from backend.src.services.trainer_service import utc_now

PENDING = "PENDING"
APPLIED = "APPLIED"
SUPERSEDED = "SUPERSEDED"

NOT_FOUND_MESSAGE = "No encontramos esta sesión entre las de tus alumnos activos."
IN_PROGRESS_MESSAGE = "La sesión todavía está en curso; vas a poder ajustarla cuando el alumno la finalice."
STALE_ROUTINE_MESSAGE = "La rutina del alumno cambió desde esta sesión; ajustala desde la edición de la rutina."
MISSING_DAY_MESSAGE = "Este día ya no forma parte de la rutina vigente del alumno."
DRAFT_PENDING_MESSAGE = (
    "La rutina del alumno tiene un borrador sin confirmar. Confirmalo o descartalo antes de ajustar la próxima sesión."
)
NO_CHANGES_MESSAGE = "No hiciste cambios: modificá algún ejercicio o agregá una nota."
NO_MATERIALS_MESSAGE = '"{name}" no tiene alternativa "Sin materiales"'


def _owned_finished_session(db: Session, user: User, session_id: str) -> tuple[WorkoutSession, TrainingRelationship]:
    trainer = get_trainer_profile(db, user)
    row = db.execute(
        select(WorkoutSession, TrainingRelationship)
        .join(TrainingRelationship, WorkoutSession.relationship_id == TrainingRelationship.id)
        .where(
            WorkoutSession.id == session_id,
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
    ).first()
    if row is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, NOT_FOUND_MESSAGE)
    session, relationship = row
    if session.finished_at is None:
        raise RoutineTemplateError(status.HTTP_409_CONFLICT, IN_PROGRESS_MESSAGE)
    return session, relationship


def _current_routine(db: Session, relationship_id: str) -> StudentRoutine | None:
    return db.scalar(
        select(StudentRoutine).where(
            StudentRoutine.relationship_id == relationship_id,
            StudentRoutine.status != "UNASSIGNED",
        )
    )


def _day_index(routine: StudentRoutine, day_name: str) -> int | None:
    return next((index for index, day in enumerate(routine.days) if day["name"] == day_name), None)


def _adjustable_routine(db: Session, relationship: TrainingRelationship, persist: bool) -> StudentRoutine | None:
    """Copia de la rutina del alumno.

    Si el entrenador todavía no la abrió (US-14), se crea solo con `persist`; si no, se arma una copia
    transitoria: crearla cambia la rutina activa del alumno y alteraría una sesión en curso.
    """
    routine = _current_routine(db, relationship.id)
    if routine is not None:
        return routine
    if persist:
        try:
            return ensure_routine(db, relationship)
        except RoutineTemplateError:
            return None
    source = _assignable_source(db, relationship.initial_routine_id)
    if source is None or source.trainer_id != relationship.trainer_id:
        return None
    transient = StudentRoutine(relationship_id=relationship.id, draft_version=0)
    _seed(transient, source)
    return transient


def _blocked_reason(
    routine: StudentRoutine | None, relationship: TrainingRelationship, session: WorkoutSession
) -> str | None:
    # Antes de crearse la copia, la sesión referencia la rutina asignada (relationship.initial_routine_id).
    if routine is None or session.routine_id not in {routine.id, relationship.initial_routine_id}:
        return STALE_ROUTINE_MESSAGE
    if _day_index(routine, session.day_name) is None:
        return MISSING_DAY_MESSAGE
    if routine.draft is not None:
        return DRAFT_PENDING_MESSAGE
    return None


def _live_adjustment(db: Session, relationship_id: str, day_name: str) -> SessionAdjustment | None:
    """El ajuste pendiente, o el aplicado que el alumno todavía no entrenó."""
    adjustment = db.scalar(
        select(SessionAdjustment)
        .where(
            SessionAdjustment.relationship_id == relationship_id,
            SessionAdjustment.day_name == day_name,
            SessionAdjustment.status.in_([PENDING, APPLIED]),
        )
        .order_by(SessionAdjustment.created_at.desc())
        .limit(1)
    )
    if adjustment is None or adjustment.status == PENDING:
        return adjustment
    return None if _trained_since(db, adjustment) else adjustment


def _trained_since(db: Session, adjustment: SessionAdjustment) -> bool:
    return (
        db.scalar(
            select(WorkoutSession.id)
            .where(
                WorkoutSession.relationship_id == adjustment.relationship_id,
                WorkoutSession.routine_id == adjustment.student_routine_id,
                WorkoutSession.day_name == adjustment.day_name,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at >= adjustment.applied_at,
            )
            .limit(1)
        )
        is not None
    )


def _adjustment_view(adjustment: SessionAdjustment) -> AdjustmentView:
    return AdjustmentView(
        id=adjustment.id,
        status=adjustment.status,
        note=adjustment.note,
        changed_exercise_ids=adjustment.changed_exercise_ids,
        created_at=adjustment.created_at,
        applied_at=adjustment.applied_at,
    )


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def _exercise_names(db: Session, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    return {ex.id: ex.name for ex in db.scalars(select(Exercise).where(Exercise.id.in_(ids)))}


def get_adjustment_context(db: Session, user: User, session_id: str) -> SessionAdjustmentContext:
    session, relationship = _owned_finished_session(db, user, session_id)
    routine = _adjustable_routine(db, relationship, persist=False)
    reason = _blocked_reason(routine, relationship, session)

    logs = list(
        db.scalars(
            select(WorkoutSetLog)
            .where(WorkoutSetLog.session_id == session.id)
            .order_by(WorkoutSetLog.recorded_at, WorkoutSetLog.set_number)
        )
    )
    logged: dict[str, LoggedExercise] = {}
    for log in logs:
        item = logged.setdefault(
            log.exercise_id, LoggedExercise(exercise_id=log.exercise_id, exercise_name=log.exercise_name, sets=[])
        )
        item.sets.append(
            LoggedSet(
                set_number=log.set_number,
                reps_completed=log.reps_completed,
                weight_kg=float(log.weight_kg) if log.weight_kg is not None else None,
            )
        )

    pain_zones = [
        SessionPainZone(
            zone=zone.zone,
            zone_label=_capitalize(BODY_AREAS_ES.get(canonical_zone_key(zone.zone) or "", zone.zone)),
            intensity=zone.intensity,
            exercise_name=report.exercise.name if report.exercise else None,
            context=report.context,
        )
        for report in db.scalars(
            select(BodyMapPainReport)
            .where(BodyMapPainReport.session_id == session.id)
            .order_by(BodyMapPainReport.created_at)
        )
        for zone in report.zones
        if zone.intensity != "NORMAL"
    ]

    replacement_logs = list(
        db.scalars(
            select(ExerciseReplacementLog).where(
                ExerciseReplacementLog.student_id == session.student_id,
                ExerciseReplacementLog.routine_id == session.routine_id,
                ExerciseReplacementLog.day_name == session.day_name,
                ExerciseReplacementLog.session_date.in_({session.started_at.date(), session.finished_at.date()}),
            )
        )
    )

    live = _live_adjustment(db, relationship.id, session.day_name)
    if routine is not None and reason in (None, DRAFT_PENDING_MESSAGE):
        day = live.blocks if live is not None and live.status == PENDING else routine.days[_day_index(routine, session.day_name)]["blocks"]
    else:
        day = []

    names = _exercise_names(
        db,
        {entry["exercise_id"] for block in day for entry in block["exercises"]}
        | {log.original_exercise_id for log in replacement_logs}
        | {log.replacement_exercise_id for log in replacement_logs if log.replacement_exercise_id},
    )
    blocks = [
        AdjustmentBlock(
            name=block["name"],
            estimated_duration_minutes=block.get("estimated_duration_minutes"),
            exercises=[
                AdjustmentEntry(
                    exercise_id=entry["exercise_id"],
                    exercise_name=names.get(entry["exercise_id"], ""),
                    sets=entry["sets"],
                    reps=entry["reps"],
                    rest_seconds=entry["rest_seconds"],
                    target_weight_kg=entry.get("target_weight_kg"),
                )
                for entry in block["exercises"]
            ],
        )
        for block in day
    ]

    return SessionAdjustmentContext(
        session_id=session.id,
        day_name=session.day_name,
        started_at=session.started_at,
        finished_at=session.finished_at,
        rpe=session.rpe,
        logged_exercises=list(logged.values()),
        pain_zones=pain_zones,
        replacement_requests=[
            ReplacementRequest(
                original_exercise_id=log.original_exercise_id,
                original_exercise_name=names.get(log.original_exercise_id, ""),
                replacement_exercise_name=names.get(log.replacement_exercise_id) if log.replacement_exercise_id else None,
            )
            for log in replacement_logs
        ],
        blocks=blocks,
        can_adjust=reason is None,
        blocked_reason=reason,
        current_adjustment=_adjustment_view(live) if live else None,
    )


def _changed_ids(before: list[dict], after: list[dict]) -> list[str]:
    """Ejercicios del día nuevo que no estaban idénticos (misma posición y parámetros) en el anterior."""
    previous = {
        (bi, ei): entry for bi, block in enumerate(before) for ei, entry in enumerate(block["exercises"])
    }
    changed: list[str] = []
    for bi, block in enumerate(after):
        for ei, entry in enumerate(block["exercises"]):
            if previous.get((bi, ei)) != entry and entry["exercise_id"] not in changed:
                changed.append(entry["exercise_id"])
    return changed


def _validate(db: Session, relationship: TrainingRelationship, routine: StudentRoutine, days: list[dict]) -> None:
    retained = {entry["exercise_id"] for day in routine.days for block in day["blocks"] for entry in block["exercises"]}
    exercises = _validate_draft_content(db, relationship, days, retained)
    if routine.has_no_materials_alternative:
        errors = [
            {
                "field": f"days.{di}.blocks.{bi}.exercises.{ei}.exercise_id",
                "message": NO_MATERIALS_MESSAGE.format(name=exercises[entry["exercise_id"]].name),
            }
            for di, day in enumerate(days)
            for bi, block in enumerate(day["blocks"])
            for ei, entry in enumerate(block["exercises"])
            if entry["exercise_id"] not in retained and not exercises[entry["exercise_id"]].has_no_materials_alternative
        ]
        if errors:
            raise RoutineTemplateError(422, VALIDATION_ERROR_MESSAGE, errors)


def _apply(db: Session, adjustment: SessionAdjustment) -> None:
    relationship = db.get(TrainingRelationship, adjustment.relationship_id)
    routine = _adjustable_routine(db, relationship, persist=True) if relationship else None
    index = _day_index(routine, adjustment.day_name) if routine is not None else None
    if index is None:
        adjustment.status = SUPERSEDED
        return
    adjustment.student_routine_id = routine.id
    days = deepcopy(routine.days)
    days[index]["blocks"] = deepcopy(adjustment.blocks)
    now = utc_now()
    snapshot = {
        "name": routine.name,
        "duration_weeks": routine.duration_weeks,
        "intensity": routine.intensity,
        "has_no_materials_alternative": routine.has_no_materials_alternative,
        "desired_weekly_volume": routine.desired_weekly_volume,
        "days": days,
    }
    changes = _diff(routine, snapshot)
    changes["session_adjustment_id"] = adjustment.id
    db.add(
        RoutineChangeLog(
            student_routine_id=routine.id, trainer_id=adjustment.trainer_id, confirmed_at=now, changes=changes
        )
    )
    routine.days = days
    routine.draft_version += 1
    routine.updated_at = now
    for previous in db.scalars(
        select(SessionAdjustment).where(
            SessionAdjustment.relationship_id == adjustment.relationship_id,
            SessionAdjustment.day_name == adjustment.day_name,
            SessionAdjustment.status == APPLIED,
            SessionAdjustment.id != adjustment.id,
        )
    ):
        previous.status = SUPERSEDED
    adjustment.status = APPLIED
    adjustment.applied_at = now


def save_adjustment(db: Session, user: User, session_id: str, payload: AdjustmentInput) -> AdjustmentView:
    session, relationship = _owned_finished_session(db, user, session_id)
    in_progress = db.scalar(
        select(WorkoutSession.id)
        .where(WorkoutSession.relationship_id == relationship.id, WorkoutSession.finished_at.is_(None))
        .order_by(WorkoutSession.started_at.desc())
        .limit(1)
    )
    routine = _adjustable_routine(db, relationship, persist=in_progress is None)
    reason = _blocked_reason(routine, relationship, session)
    if reason is not None:
        raise RoutineTemplateError(status.HTTP_409_CONFLICT, reason)

    index = _day_index(routine, session.day_name)
    blocks = [block.model_dump() for block in payload.blocks]
    days = deepcopy(routine.days)
    days[index]["blocks"] = blocks
    _validate(db, relationship, routine, days)

    changed = _changed_ids(routine.days[index]["blocks"], blocks)
    if not changed and payload.note is None:
        raise RoutineTemplateError(422, NO_CHANGES_MESSAGE)

    for pending in db.scalars(
        select(SessionAdjustment).where(
            SessionAdjustment.relationship_id == relationship.id,
            SessionAdjustment.day_name == session.day_name,
            SessionAdjustment.status == PENDING,
        )
    ):
        pending.status = SUPERSEDED

    adjustment = SessionAdjustment(
        relationship_id=relationship.id,
        student_routine_id=routine.id,  # None si la copia se crea al aplicar
        source_session_id=session.id,
        blocking_session_id=in_progress,
        trainer_id=relationship.trainer_id,
        day_name=session.day_name,
        note=payload.note,
        blocks=blocks,
        changed_exercise_ids=changed,
        status=PENDING,
        created_at=utc_now(),
    )
    db.add(adjustment)
    db.flush()
    if in_progress is None:
        _apply(db, adjustment)
    db.commit()
    db.refresh(adjustment)
    return _adjustment_view(adjustment)


def apply_pending_adjustments(db: Session, relationship_id: str, finished_session_id: str | None = None) -> bool:
    """Aplica los ajustes que esperaban el fin de una sesión.

    Al finalizar una sesión se aplican los que esperaban esa sesión; al iniciar una nueva, todos
    (si el alumno empieza otra, la sesión que bloqueaba quedó abandonada).
    """
    query = select(SessionAdjustment).where(
        SessionAdjustment.relationship_id == relationship_id, SessionAdjustment.status == PENDING
    )
    if finished_session_id is not None:
        query = query.where(SessionAdjustment.blocking_session_id == finished_session_id)
    pending = list(db.scalars(query.order_by(SessionAdjustment.created_at)))
    if not pending:
        return False
    for adjustment in pending:
        _apply(db, adjustment)
        db.flush()
    db.commit()
    return True


def list_student_adjustments(db: Session, user: User) -> list[StudentAdjustmentNotice]:
    """Ajustes aplicados que el alumno todavía no entrenó, para mostrar "Ajustado por tu entrenador"."""
    profile = get_student_profile(db, user)
    relationship = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.student_id == profile.id, TrainingRelationship.status == "ACTIVE"
        )
    )
    if relationship is None:
        return []
    routine = _current_routine(db, relationship.id)
    if routine is None:
        return []
    notices: list[StudentAdjustmentNotice] = []
    for day in routine.days:
        adjustment = _live_adjustment(db, relationship.id, day["name"])
        if adjustment is not None and adjustment.status == APPLIED and adjustment.student_routine_id == routine.id:
            notices.append(
                StudentAdjustmentNotice(
                    day_name=adjustment.day_name,
                    note=adjustment.note,
                    exercise_ids=adjustment.changed_exercise_ids,
                    adjusted_at=adjustment.applied_at,
                )
            )
    return notices
