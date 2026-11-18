"""US-24: métricas planificadas vs realizadas de una sesión finalizada, y vs la sesión previa del mismo día."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.assigned_routine import AssignedRoutine
from backend.src.models.exercise import Exercise
from backend.src.models.exercise_replacement_log import ExerciseReplacementLog
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_routine import StudentRoutine
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import (
    WorkoutSession,
    WorkoutSessionSnapshot,
    WorkoutSetLog,
)
from backend.src.schemas.trainer_student import (
    ExerciseComparison,
    PerformedMetrics,
    PlannedMetrics,
    SessionComparison,
)
from backend.src.services.daily_routine_tracking_service import session_view
from backend.src.services.trainer_service import (
    TrainerProfileError,
    get_or_create_profile,
)
from backend.src.services.trainer_student_service import TrainerStudentError

NOT_FOUND_MESSAGE = "No encontramos esta sesión entre las de tus alumnos activos."
IN_PROGRESS_MESSAGE = "La sesión todavía está en curso; vas a poder compararla cuando el alumno la finalice."


def _planned_entries(db: Session, routine_id: str, day_name: str) -> list[dict]:
    """Ejercicios planificados del día en la versión vigente de la rutina (copia del alumno, plantilla o asignada)."""
    student_routine = db.get(StudentRoutine, routine_id)
    if student_routine is not None:
        for day in student_routine.days:
            if day["name"] == day_name:
                return [
                    {
                        "exercise_id": entry["exercise_id"],
                        "sets": entry["sets"],
                        "reps": entry["reps"],
                        "target_weight_kg": entry.get("target_weight_kg"),
                    }
                    for block in day["blocks"]
                    for entry in block["exercises"]
                ]
        return []
    source = db.get(RoutineTemplate, routine_id) or db.get(AssignedRoutine, routine_id)
    if source is None:
        return []
    for day in source.days:
        if day.name == day_name:
            return [
                {
                    "exercise_id": entry.exercise_id,
                    "sets": entry.sets,
                    "reps": entry.reps,
                    "target_weight_kg": entry.target_weight_kg,
                }
                for block in day.blocks
                for entry in block.exercises
            ]
    return []


def _planned_from_blocks(blocks: list[dict]) -> tuple[list[dict], int | None]:
    entries = [
        {
            "exercise_id": entry["exercise_id"],
            "sets": entry["sets"],
            "reps": entry["reps"],
            "target_weight_kg": entry.get("target_weight_kg"),
        }
        for block in blocks
        for entry in block.get("exercises", [])
    ]
    minutes = [
        block.get("estimated_duration_minutes")
        for block in blocks
        if block.get("estimated_duration_minutes") is not None
    ]
    planned_duration = sum(int(m) * 60 for m in minutes) if minutes else None
    return entries, planned_duration


def _planned_day_snapshot(db: Session, routine_id: str, day_name: str) -> tuple[list[dict], int | None]:
    """Resuelve ejercicios y duración planificada desde la rutina vigente (fallback sin snapshot)."""
    student_routine = db.get(StudentRoutine, routine_id)
    if student_routine is not None:
        for day in student_routine.days:
            if day["name"] == day_name:
                return _planned_from_blocks(day["blocks"])
        return [], None
    source = db.get(RoutineTemplate, routine_id) or db.get(AssignedRoutine, routine_id)
    if source is None:
        return [], None
    for day in source.days:
        if day.name == day_name:
            entries = [
                {
                    "exercise_id": entry.exercise_id,
                    "sets": entry.sets,
                    "reps": entry.reps,
                    "target_weight_kg": entry.target_weight_kg,
                }
                for block in day.blocks
                for entry in block.exercises
            ]
            minutes = [
                block.estimated_duration_minutes
                for block in day.blocks
                if block.estimated_duration_minutes is not None
            ]
            planned_duration = sum(int(m) * 60 for m in minutes) if minutes else None
            return entries, planned_duration
    return [], None


def _number(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _performed(logs: list[WorkoutSetLog]) -> PerformedMetrics:
    ordered = sorted(logs, key=lambda log: (log.set_number, log.recorded_at))
    weights = [log.weight_kg for log in ordered if log.weight_kg is not None]
    durations = [log.duration_seconds for log in ordered if log.duration_seconds is not None]
    volume = Decimal(0)
    for log in ordered:
        reps = _number(log.reps_completed)
        if reps is not None and log.weight_kg is not None:
            volume += reps * log.weight_kg
    return PerformedMetrics(
        sets_completed=len(ordered),
        reps=[log.reps_completed for log in ordered],
        max_weight_kg=float(max(weights)) if weights else None,
        volume_kg=float(volume),
        total_duration_seconds=sum(durations) if durations else None,
    )


def _logs_by_exercise(db: Session, session: WorkoutSession) -> dict[str, list[WorkoutSetLog]]:
    grouped: dict[str, list[WorkoutSetLog]] = defaultdict(list)
    for log in db.scalars(select(WorkoutSetLog).where(WorkoutSetLog.session_id == session.id)):
        grouped[log.exercise_id].append(log)
    return grouped


def _owned_session(db: Session, user: User, session_id: str) -> WorkoutSession:
    try:
        trainer = get_or_create_profile(db, user)
    except TrainerProfileError as error:
        raise TrainerStudentError(error.status_code, error.detail) from error
    session = db.scalar(
        select(WorkoutSession)
        .join(TrainingRelationship, WorkoutSession.relationship_id == TrainingRelationship.id)
        .where(
            WorkoutSession.id == session_id,
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if session is None:
        raise TrainerStudentError(404, NOT_FOUND_MESSAGE)
    if session.finished_at is None:
        raise TrainerStudentError(409, IN_PROGRESS_MESSAGE)
    return session


def _replacements(db: Session, session: WorkoutSession) -> dict[str, str]:
    """original → reemplazo elegido por el alumno durante la sesión (US-54)."""
    dates = {session.started_at.date(), session.finished_at.date()}
    resolved: dict[str, str] = {
        log.original_exercise_id: log.replacement_exercise_id
        for log in db.scalars(
            select(ExerciseReplacementLog).where(
                ExerciseReplacementLog.session_id.is_(None),
                ExerciseReplacementLog.student_id == session.student_id,
                ExerciseReplacementLog.routine_id == session.routine_id,
                ExerciseReplacementLog.day_name == session.day_name,
                ExerciseReplacementLog.session_date.in_(dates),
                ExerciseReplacementLog.replacement_exercise_id.is_not(None),
            )
        )
    }
    for log in db.scalars(
        select(ExerciseReplacementLog).where(
            ExerciseReplacementLog.session_id == session.id,
            ExerciseReplacementLog.replacement_exercise_id.is_not(None),
        )
    ):
        resolved[log.original_exercise_id] = log.replacement_exercise_id
    return resolved


def compare_session(db: Session, user: User, session_id: str) -> SessionComparison:
    session = _owned_session(db, user, session_id)
    snapshot = db.get(WorkoutSessionSnapshot, session.id)
    assignment_id = snapshot.routine_assignment_id if snapshot is not None else None
    if assignment_id is not None:
        previous = db.scalar(
            select(WorkoutSession)
            .join(WorkoutSessionSnapshot, WorkoutSessionSnapshot.session_id == WorkoutSession.id)
            .where(
                WorkoutSession.relationship_id == session.relationship_id,
                WorkoutSessionSnapshot.routine_assignment_id == assignment_id,
                WorkoutSession.day_name == session.day_name,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at < session.started_at,
            )
            .order_by(WorkoutSession.started_at.desc())
            .limit(1)
        )
    else:
        previous = db.scalar(
            select(WorkoutSession)
            .where(
                WorkoutSession.relationship_id == session.relationship_id,
                WorkoutSession.routine_id == session.routine_id,
                WorkoutSession.day_name == session.day_name,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at < session.started_at,
            )
            .order_by(WorkoutSession.started_at.desc())
            .limit(1)
        )
    current_logs = _logs_by_exercise(db, session)
    previous_logs = _logs_by_exercise(db, previous) if previous else {}
    if snapshot is not None:
        planned, planned_duration_seconds = _planned_from_blocks(snapshot.planned_blocks)
    else:
        planned, planned_duration_seconds = _planned_day_snapshot(db, session.routine_id, session.day_name)
    replacements = _replacements(db, session)

    names = {
        log.exercise_id: log.exercise_name
        for logs in (*current_logs.values(), *previous_logs.values())
        for log in logs
    }
    missing = {entry["exercise_id"] for entry in planned} | set(replacements.values())
    missing -= names.keys()
    if missing:
        names.update({ex.id: ex.name for ex in db.scalars(select(Exercise).where(Exercise.id.in_(missing)))})

    def metrics(logs: dict[str, list[WorkoutSetLog]], exercise_id: str) -> PerformedMetrics | None:
        return _performed(logs[exercise_id]) if exercise_id in logs else None

    exercises: list[ExerciseComparison] = []
    seen: set[str] = set()
    for entry in planned:
        original_id = entry["exercise_id"]
        performed_id = original_id
        replaced_name = None
        if original_id not in current_logs and replacements.get(original_id) in current_logs:
            performed_id = replacements[original_id]
            replaced_name = names.get(original_id)
        if performed_id in seen:
            continue
        seen.add(performed_id)
        target = entry["target_weight_kg"]
        exercises.append(
            ExerciseComparison(
                exercise_id=performed_id,
                exercise_name=names.get(performed_id, ""),
                replaced_exercise_name=replaced_name,
                planned=PlannedMetrics(
                    sets=entry["sets"],
                    reps=entry["reps"],
                    target_weight_kg=float(target) if target is not None else None,
                ),
                performed=metrics(current_logs, performed_id),
                previous=metrics(previous_logs, performed_id),
            )
        )
    # Ejercicios realizados fuera de lo planificado (p. ej. reemplazos adicionales o ejercicios históricos).
    for exercise_id in current_logs:
        if exercise_id not in seen:
            seen.add(exercise_id)
            exercises.append(
                ExerciseComparison(
                    exercise_id=exercise_id,
                    exercise_name=names[exercise_id],
                    performed=metrics(current_logs, exercise_id),
                    previous=metrics(previous_logs, exercise_id),
                )
            )
    for exercise_id in previous_logs:
        if exercise_id not in seen:
            seen.add(exercise_id)
            exercises.append(
                ExerciseComparison(
                    exercise_id=exercise_id,
                    exercise_name=names.get(exercise_id, ""),
                    performed=None,
                    previous=metrics(previous_logs, exercise_id),
                )
            )

    def total(logs: dict[str, list[WorkoutSetLog]]) -> float:
        return sum((_performed(items).volume_kg for items in logs.values()), 0.0)

    return SessionComparison(
        session=session_view(session),
        previous_session=session_view(previous) if previous else None,
        planned_duration_seconds=planned_duration_seconds,
        volume_kg=total(current_logs),
        previous_volume_kg=total(previous_logs) if previous else None,
        exercises=exercises,
    )
