"""Resumen de una sesión de entrenamiento finalizada (US-63).

El resumen se calcula a demanda a partir de la sesión, sus series registradas
y la rutina activa del alumno; no se persiste. Las reglas de cálculo están
documentadas en `taskify/specs/008-workout-feedback-and-communication/research.md`.
"""

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.services.routine_template_service import (
    VALIDATION_ERROR_STATUS,
    RoutineTemplateError,
    _resolve_student_active_routine,
    get_student_profile,
)

_LEADING_NUMBER = re.compile(r"^\s*(\d+(?:[.,]\d+)?)")


def parse_reps(value: str | None) -> float:
    """Devuelve el número inicial de las repeticiones registradas ("8-10" → 8); 0 si no hay."""
    match = _LEADING_NUMBER.match(value or "")
    return float(match.group(1).replace(",", ".")) if match else 0.0


def set_tonnage(log: WorkoutSetLog) -> float:
    if log.weight_kg is None:
        return 0.0
    return float(log.weight_kg) * parse_reps(log.reps_completed)


def session_tonnage(logs: list[WorkoutSetLog]) -> float:
    return sum(set_tonnage(log) for log in logs)


def _session_logs(db: Session, session_id: str) -> list[WorkoutSetLog]:
    return list(
        db.scalars(
            select(WorkoutSetLog)
            .where(WorkoutSetLog.session_id == session_id)
            .order_by(WorkoutSetLog.recorded_at, WorkoutSetLog.id)
        )
    )


def _programmed_sets(db: Session, user: User, session: WorkoutSession) -> int | None:
    """Series programadas del día, solo si la rutina activa sigue siendo la de la sesión."""
    try:
        _, routine_view = _resolve_student_active_routine(db, user)
    except RoutineTemplateError:
        return None
    routine_id = routine_view["id"] if isinstance(routine_view, dict) else routine_view.id
    if routine_id != session.routine_id:
        return None

    def attr(item: Any, name: str) -> Any:
        return item[name] if isinstance(item, dict) else getattr(item, name)

    days = [day for day in attr(routine_view, "days") if attr(day, "name") == session.day_name]
    if not days:
        return None
    return sum(
        int(attr(entry, "sets"))
        for day in days
        for block in attr(day, "blocks")
        for entry in attr(block, "exercises")
    )


def _session_personal_records(
    db: Session, session: WorkoutSession, logs: list[WorkoutSetLog]
) -> list[dict[str, Any]]:
    """PRs logrados en la sesión: el máximo de la sesión supera todo lo registrado antes."""
    by_exercise: dict[str, list[WorkoutSetLog]] = defaultdict(list)
    for log in logs:
        by_exercise[log.exercise_id].append(log)

    records: list[dict[str, Any]] = []
    for exercise_id, exercise_logs in by_exercise.items():
        best = max(exercise_logs, key=lambda log: (log.weight_kg or Decimal(0), log.recorded_at))
        best_weight = best.weight_kg or Decimal(0)
        if best_weight <= 0:
            continue
        first_recorded_at = min(log.recorded_at for log in exercise_logs)
        previous_max = db.scalar(
            select(WorkoutSetLog.weight_kg)
            .where(
                WorkoutSetLog.student_id == session.student_id,
                WorkoutSetLog.exercise_id == exercise_id,
                WorkoutSetLog.recorded_at < first_recorded_at,
                WorkoutSetLog.weight_kg > 0,
                (WorkoutSetLog.session_id.is_(None)) | (WorkoutSetLog.session_id != session.id),
            )
            .order_by(WorkoutSetLog.weight_kg.desc())
            .limit(1)
        )
        if previous_max is not None and best_weight <= previous_max:
            continue
        records.append(
            {
                "exercise_id": exercise_id,
                "exercise_name": best.exercise_name,
                "weight_kg": float(best_weight),
                "reps_completed": best.reps_completed,
                "previous_weight_kg": float(previous_max) if previous_max is not None else None,
            }
        )
    return sorted(records, key=lambda record: record["exercise_name"])


def _history_comparison(db: Session, session: WorkoutSession, tonnage: float) -> dict[str, Any]:
    """Promedio de tonelaje de las sesiones anteriores del mismo día de la misma rutina."""
    previous_sessions = db.scalars(
        select(WorkoutSession).where(
            WorkoutSession.student_id == session.student_id,
            WorkoutSession.routine_id == session.routine_id,
            WorkoutSession.day_name == session.day_name,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSession.started_at < session.started_at,
            WorkoutSession.id != session.id,
        )
    ).all()

    tonnages: list[float] = []
    for previous in previous_sessions:
        previous_logs = _session_logs(db, previous.id)
        if previous_logs:
            tonnages.append(session_tonnage(previous_logs))

    if not tonnages:
        return {"previous_sessions_count": 0, "average_tonnage_kg": None, "tonnage_delta_percent": None}

    average = sum(tonnages) / len(tonnages)
    delta = round((tonnage - average) / average * 100, 1) if average > 0 else None
    return {
        "previous_sessions_count": len(tonnages),
        "average_tonnage_kg": round(average, 2),
        "tonnage_delta_percent": delta,
    }


def build_student_session_summary(db: Session, user: User, session_id: str) -> dict[str, Any]:
    profile = get_student_profile(db, user)
    session = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id,
            WorkoutSession.student_id == profile.id,
        )
    )
    if session is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No encontramos este entrenamiento.")
    if session.finished_at is None:
        raise RoutineTemplateError(
            VALIDATION_ERROR_STATUS,
            "El resumen está disponible cuando finalizás el entrenamiento.",
        )

    logs = _session_logs(db, session.id)
    tonnage = session_tonnage(logs)
    duration = max(0, int((session.finished_at - session.started_at).total_seconds()))
    return {
        "session_id": session.id,
        "day_name": session.day_name,
        "started_at": session.started_at,
        "finished_at": session.finished_at,
        "duration_seconds": duration,
        "rpe": session.rpe,
        "total_tonnage_kg": round(tonnage, 2),
        "completed_sets": len(logs),
        "programmed_sets": _programmed_sets(db, user, session),
        "personal_records": _session_personal_records(db, session, logs),
        "history": _history_comparison(db, session, tonnage),
    }
