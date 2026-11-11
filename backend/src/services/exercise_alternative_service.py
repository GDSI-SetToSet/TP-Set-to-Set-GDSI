from datetime import timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.exercise import Exercise
from backend.src.models.exercise_replacement_log import ExerciseReplacementLog
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.exercise_alternative import ReplacementInput
from backend.src.services import routine_template_service as routines
from backend.src.services import safe_variant_service as safe
from backend.src.services.exercise_service import ExerciseError
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.trainer_service import utc_now


def _group(value: str) -> str:
    return value.strip().lower()


def _context(db: Session, user: User, exercise_id: str) -> tuple[TrainingRelationship, str, Exercise]:
    """Vínculo ACTIVE (403), rutina vigente y ejercicio dentro de ella (404)."""
    profile = get_student_profile(db, user)
    if not safe.active_relationship(db, profile.id):
        raise ExerciseError(status.HTTP_403_FORBIDDEN, "No tenés un vínculo activo con un entrenador.")
    try:
        relationship, view = routines._resolve_student_active_routine(db, user)
    except routines.RoutineTemplateError as error:
        raise ExerciseError(error.status_code, error.detail) from error
    in_routine = {e.id: e for *_, e in routines._iter_routine_exercises(view)}
    if exercise_id not in in_routine:
        raise ExerciseError(status.HTTP_404_NOT_FOUND, "Ejercicio no encontrado en tu rutina.")
    routine_id = view.id if hasattr(view, "id") else view["id"]
    return relationship, routine_id, in_routine[exercise_id]


def _alternatives(db: Session, relationship: TrainingRelationship, original: Exercise) -> list[dict]:
    """Calculadas en cada consulta (research D15); resolución pura de US-53: sin casos ni notificaciones."""
    zones = safe.student_zones(db, relationship.student_id)
    group = _group(original.target_muscle_group)
    result = []
    candidates = db.scalars(
        select(Exercise)
        .where(Exercise.trainer_id == original.trainer_id, Exercise.deleted_at.is_(None), Exercise.id != original.id)
        .order_by(Exercise.name, Exercise.id)
    )
    for candidate in candidates:
        if _group(candidate.target_muscle_group) != group:
            continue
        outcome, variant = safe.resolve_variant(db, candidate, zones)
        if outcome == "BLOCKED":
            continue
        result.append(
            {
                "exercise_id": candidate.id,
                "name": candidate.name,
                "equipment_needed": candidate.equipment_needed,
                "variant": {"exercise_id": variant.id, "name": variant.name} if variant else None,
            }
        )
    return result


def list_alternatives(db: Session, user: User, exercise_id: str) -> dict:
    relationship, _, original = _context(db, user, exercise_id)
    items = _alternatives(db, relationship, original)
    return {"alternatives": items, "can_skip": not items}


def record_replacement(db: Session, user: User, payload: ReplacementInput) -> ExerciseReplacementLog:
    relationship, routine_id, original = _context(db, user, payload.original_exercise_id)
    chosen = payload.replacement_exercise_id
    if chosen is not None:
        valid = {a["exercise_id"]: a for a in _alternatives(db, relationship, original)}
        if chosen not in valid:
            raise ExerciseError(
                422,
                "Datos inválidos",
                [{"field": "replacement_exercise_id", "message": "La alternativa no está disponible para este ejercicio."}],
            )
        if valid[chosen]["variant"]:  # la alternativa es de riesgo para el alumno: se hace su variante segura
            chosen = valid[chosen]["variant"]["exercise_id"]
    today = utc_now().date()
    log = db.scalar(
        select(ExerciseReplacementLog).where(
            ExerciseReplacementLog.student_id == relationship.student_id,
            ExerciseReplacementLog.routine_id == routine_id,
            ExerciseReplacementLog.day_name == payload.day_name,
            ExerciseReplacementLog.session_date == today,
            ExerciseReplacementLog.original_exercise_id == original.id,
        )
    )
    if log is None:  # select-then-update: portable entre SQLite y PostgreSQL
        log = ExerciseReplacementLog(
            student_id=relationship.student_id,
            routine_id=routine_id,
            day_name=payload.day_name,
            session_date=today,
            original_exercise_id=original.id,
        )
        db.add(log)
    log.replacement_exercise_id = chosen
    log.updated_at = utc_now()
    db.commit()
    db.refresh(log)
    return log


def is_replacement_today(db: Session, student_id: str, routine_id: str, day_name: str, exercise_id: str) -> Exercise | None:
    """Ejercicio elegido hoy (o ayer UTC) como reemplazo (permite registrar series con el ejercicio realmente realizado)."""
    today = utc_now().date()  # ayer UTC también vale: en Argentina el día UTC cambia a las 21:00
    found = db.scalar(
        select(ExerciseReplacementLog.id).where(
            ExerciseReplacementLog.student_id == student_id,
            ExerciseReplacementLog.routine_id == routine_id,
            ExerciseReplacementLog.day_name == day_name,
            ExerciseReplacementLog.session_date.in_([today, today - timedelta(days=1)]),
            ExerciseReplacementLog.replacement_exercise_id == exercise_id,
        )
    )
    return db.get(Exercise, exercise_id) if found else None
