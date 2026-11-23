"""Servicio unificado de récords personales (US-65 FR-001a, US-59, US-63, US-67).

Regla única del dominio (US-65 FR-001a):
- La primera sesión/carga de un ejercicio establece la marca base inicial y no constituye un PR.
- Existe un nuevo récord personal cuando una marca posterior supera la mejor anterior:
  más peso (kg), o el mismo peso con mayor cantidad de repeticiones numéricas (incluye ejercicios
  sin carga adicional con peso 0 kg).
- Las series se agrupan por sesión (`session_id`) o por fecha UTC si son registros sueltos sin sesión.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.personal_record import PersonalRecord
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.services.daily_routine_tracking_service import _as_utc
from backend.src.services.session_comparison_service import _number

Mark = tuple[float, int]  # (weight_kg, reps); bodyweight tiene peso 0.0


@dataclass(frozen=True)
class PrEvent:
    group_key: tuple[str, Any]
    day: date
    best: Mark
    previous: Mark
    log: WorkoutSetLog


@dataclass(frozen=True)
class LivePrEvaluation:
    is_pr: bool
    previous_mark: Mark | None


def set_mark(log: WorkoutSetLog) -> Mark | None:
    """Convierte una serie en (peso_kg, reps_enteras) comparable, o None si reps no es numérico."""
    reps = _number(log.reps_completed)
    if reps is None or reps <= 0:
        return None
    return (float(log.weight_kg or 0), int(reps))


def best_mark(logs: list[WorkoutSetLog]) -> Mark | None:
    """Mejor marca de un conjunto de series (prioriza carga > 0, luego más peso y más repeticiones)."""
    sets = [mark for log in logs if (mark := set_mark(log)) is not None]
    if not sets:
        return None
    weighted = [item for item in sets if item[0] > 0]
    return max(weighted) if weighted else (0.0, max(reps for _, reps in sets))


def log_group_key(log: WorkoutSetLog) -> tuple[str, Any]:
    """Agrupa por `session_id` cuando existe para evitar mezclar sesiones en un mismo día UTC."""
    if log.session_id is not None:
        return ("session", log.session_id)
    return ("day", _as_utc(log.recorded_at).date())


def load_student_logs(
    db: Session,
    student_id: str,
    *,
    exercise_id: str | None = None,
    finished_only: bool = False,
) -> list[WorkoutSetLog]:
    """Carga cronológica de series del alumno (opcionalmente filtrada a sesiones finalizadas o sin sesión)."""
    stmt = select(WorkoutSetLog).where(WorkoutSetLog.student_id == student_id)
    if exercise_id is not None:
        stmt = stmt.where(WorkoutSetLog.exercise_id == exercise_id)
    if finished_only:
        stmt = stmt.outerjoin(WorkoutSession, WorkoutSetLog.session_id == WorkoutSession.id).where(
            WorkoutSetLog.session_id.is_(None) | WorkoutSession.finished_at.is_not(None)
        )
    stmt = stmt.order_by(WorkoutSetLog.recorded_at, WorkoutSetLog.set_number, WorkoutSetLog.id)
    return list(db.scalars(stmt))


def compute_exercise_pr_timeline(ordered_logs: list[WorkoutSetLog]) -> list[PrEvent]:
    """Devuelve la secuencia de PRs reales de un ejercicio en orden cronológico.

    La primera sesión/grupo nunca se marca como PR; solo las posteriores que superan
    la mejor marca acumulada (`best > top`).
    """
    grouped: dict[tuple[str, Any], list[WorkoutSetLog]] = {}
    for log in ordered_logs:
        grouped.setdefault(log_group_key(log), []).append(log)

    groups_with_best: list[tuple[tuple[str, Any], Mark, WorkoutSetLog]] = []
    for key, group_logs in grouped.items():
        best = best_mark(group_logs)
        if best is None:
            continue
        winning = next(log for log in group_logs if set_mark(log) == best)
        groups_with_best.append((key, best, winning))

    if len(groups_with_best) < 2:
        return []

    events: list[PrEvent] = []
    top = groups_with_best[0][1]
    for key, best, winning in groups_with_best[1:]:
        if best > top:
            events.append(
                PrEvent(
                    group_key=key,
                    day=_as_utc(winning.recorded_at).date(),
                    best=best,
                    previous=top,
                    log=winning,
                )
            )
            top = best
    return events


def evaluate_live_set_pr(
    db: Session, student_id: str, exercise_id: str, new_log: WorkoutSetLog
) -> LivePrEvaluation:
    """Evalúa si una serie recién creada constituye un nuevo PR respetando FR-001a."""
    current_mark = set_mark(new_log)
    if current_mark is None:
        return LivePrEvaluation(is_pr=False, previous_mark=None)

    all_logs = [
        log
        for log in load_student_logs(db, student_id, exercise_id=exercise_id)
        if log.id != new_log.id
    ]
    current_key = log_group_key(new_log)
    prior_logs = [log for log in all_logs if log_group_key(log) != current_key]
    prior_best = best_mark(prior_logs)
    if prior_best is None:
        # La primera sesión/carga del ejercicio fija la línea base y no es PR.
        return LivePrEvaluation(is_pr=False, previous_mark=None)

    same_session_logs = [log for log in all_logs if log_group_key(log) == current_key]
    same_session_best = best_mark(same_session_logs)
    threshold = max(prior_best, same_session_best) if same_session_best is not None else prior_best
    if current_mark > threshold:
        return LivePrEvaluation(is_pr=True, previous_mark=threshold)
    return LivePrEvaluation(is_pr=False, previous_mark=None)


def sync_personal_record(
    db: Session, student_id: str, exercise_id: str, existing_pr: PersonalRecord | None = None
) -> PersonalRecord | None:
    """Recalcula y sincroniza el récord vigente en `personal_records` a partir del historial."""
    logs = load_student_logs(db, student_id, exercise_id=exercise_id)
    timeline = compute_exercise_pr_timeline(logs)
    pr = existing_pr
    if pr is None:
        pr = db.scalar(
            select(PersonalRecord)
            .where(
                PersonalRecord.student_id == student_id,
                PersonalRecord.exercise_id == exercise_id,
            )
            .with_for_update()
        )
    if not timeline:
        if pr is not None:
            db.delete(pr)
        return None

    latest = timeline[-1].log
    weight_val = latest.weight_kg if latest.weight_kg is not None else Decimal("0.00")
    if pr is None:
        pr = PersonalRecord(
            student_id=student_id,
            exercise_id=exercise_id,
            weight_kg=weight_val,
            reps_completed=latest.reps_completed,
            workout_set_log_id=latest.id,
            achieved_at=latest.recorded_at,
        )
        db.add(pr)
    else:
        pr.weight_kg = weight_val
        pr.reps_completed = latest.reps_completed
        pr.workout_set_log_id = latest.id
        pr.achieved_at = latest.recorded_at
    return pr
