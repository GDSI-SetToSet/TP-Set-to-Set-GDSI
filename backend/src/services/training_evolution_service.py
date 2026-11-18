"""US-30: progreso del alumno para el entrenador.

Responde cuatro preguntas con datos de sus sesiones finalizadas: ¿está progresando? (progresión por ejercicio),
¿está entrenando lo que le programé? (adherencia y cumplimiento), ¿cómo le está costando? (RPE) y
¿qué tengo que ajustar? (puntos a revisar y series por grupo muscular). La semana en curso no entra en
estados, porcentajes ni tendencias.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.assigned_routine import AssignedRoutine
from backend.src.models.effort_feedback import EffortFeedback
from backend.src.models.exercise import Exercise
from backend.src.models.personal_record import PersonalRecord
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_routine import StudentRoutine
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.trainer_student import (
    AdherenceSummary,
    AdherenceWeek,
    EffortSummary,
    EvolutionPeriod,
    EvolutionSummary,
    ExercisePoint,
    ExerciseProgress,
    LastImprovement,
    MostSkipped,
    MuscleGroupSets,
    ProgressSummary,
    ReviewItem,
    ReviewSummary,
    RpePoint,
    SetResult,
    TrainingEvolution,
)
from backend.src.services import routine_template_service
from backend.src.services.abandonment_risk_service import _weekly_trainings
from backend.src.services.daily_routine_tracking_service import _as_utc
from backend.src.services.session_comparison_service import (
    _number,
    _planned_entries,
    _replacements,
)
from backend.src.services.trainer_student_service import (
    _active_relationship,
    _trainer_profile,
)

# Umbrales iniciales; se ajustan acá, no en el código de cálculo.
PERIOD_WEEKS = {"4w": 4, "12w": 12}
STATUS_WINDOW_WEEKS = 3  # ventana de "Progresando" / "Estancado" y referencia de "Bajó"
STALLED_MIN_SESSIONS = 3
DECLINE_RATIO = 0.9  # "Bajó": actual <= 90 % del máximo anterior
SKIPPED_BELOW_PCT = 70
MOST_SKIPPED_LIMIT = 3
PROGRESS_GREEN_PCT, PROGRESS_YELLOW_PCT = 50, 25
ADHERENCE_GREEN_PCT, ADHERENCE_YELLOW_PCT = 80, 60
RPE_LOW, RPE_HIGH, RPE_EXCESSIVE = 6, 8, 9
RPE_TREND_TOLERANCE = 0.5
RPE_WINDOW = 4
REVIEW_YELLOW_MAX = 2
NO_GROUP = "Sin grupo"

Best = tuple[float, int]  # (peso, repeticiones); sin carga, peso 0


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _best(logs: list[WorkoutSetLog]) -> Best | None:
    """Mejor serie de la sesión: más peso (y a igual peso, más repeticiones); sin carga, más repeticiones."""
    sets = [
        (float(log.weight_kg or 0), int(reps))
        for log in logs
        if (reps := _number(log.reps_completed)) is not None
    ]
    if not sets:
        return None  # repeticiones no numéricas ("45 seg", "al fallo"): sin métrica
    weighted = [item for item in sets if item[0] > 0]
    return max(weighted) if weighted else (0.0, max(reps for _, reps in sets))


def _main(value: Best, kind: str) -> float:
    return value[0] if kind == "max_weight" else float(value[1])


def classify(history: list[tuple[date, Best]], kind: str, current_monday: date) -> tuple[str, date | None]:
    """Estado de un ejercicio a partir de sus sesiones de semanas completas y fecha de su última mejora.

    Orden: pocos datos → bajó → progresando → estancado → sin cambios.
    """
    if len(history) < 2:
        return "few_data", None
    improvements: list[date] = []
    best = history[0][1]
    for day, value in history[1:]:
        if value > best:
            improvements.append(day)
            best = value
    window_start = current_monday - timedelta(weeks=STATUS_WINDOW_WEEKS)
    last_day, last_value = history[-1]
    last_week = _monday(last_day)
    reference = [
        _main(value, kind)
        for day, value in history
        if last_week - timedelta(weeks=STATUS_WINDOW_WEEKS) <= day < last_week
    ]
    last_improvement = improvements[-1] if improvements else None
    if reference and _main(last_value, kind) <= DECLINE_RATIO * max(reference):
        return "declined", last_improvement
    if last_improvement and last_improvement >= window_start:
        return "progressing", last_improvement
    if sum(1 for day, _ in history if day >= window_start) >= STALLED_MIN_SESSIONS:
        return "stalled", last_improvement
    return "unchanged", last_improvement


def effort_message(excessive: bool, load_up: bool, trend: str | None, avg_rpe: float | None) -> str | None:
    """Combina la carga y el RPE. Precedencia: esfuerzo excesivo → fatiga → exigir más → progreso con esfuerzo."""
    if excessive:
        return "excessive_effort"
    if avg_rpe is None:
        return None
    if not load_up and trend == "rising":
        return "fatigue"
    if avg_rpe < RPE_LOW:
        return "room_for_more"
    if load_up:
        return "progressing_effort_rising" if trend == "rising" else "progressing_with_margin"
    return None


def _result(value: Best) -> SetResult:
    return SetResult(weight=value[0] if value[0] > 0 else None, reps=value[1])


def _light(value: float, green: float, yellow: float) -> str:
    return "green" if value >= green else "yellow" if value >= yellow else "red"


def get_training_evolution(
    db: Session,
    user: User,
    student_id: str,
    period: Literal["4w", "12w", "all"] = "12w",
    group_by: Literal["session", "week"] = "week",
    muscle_group: str | None = None,
) -> TrainingEvolution:
    relationship = _active_relationship(db, _trainer_profile(db, user).id, student_id)
    now = _as_utc(routine_template_service.utc_now())
    today = now.date()
    current_monday = _monday(today)

    all_sessions = [
        (session, _as_utc(session.finished_at))
        for session in db.scalars(
            select(WorkoutSession)
            .where(
                WorkoutSession.relationship_id == relationship.id,
                WorkoutSession.student_id == student_id,
                WorkoutSession.finished_at.is_not(None),
            )
            .order_by(WorkoutSession.finished_at)
        )
    ]
    if period in PERIOD_WEEKS:
        range_start: date | None = current_monday - timedelta(weeks=PERIOD_WEEKS[period] - 1)
    else:
        range_start = _monday(all_sessions[0][1].date()) if all_sessions else None
    sessions = [(s, f) for s, f in all_sessions if range_start is None or f.date() >= range_start]
    complete = [(s, f) for s, f in sessions if _monday(f.date()) < current_monday]

    # ponytail: se cargan los logs de todo el historial del vínculo; paginar o agregar en SQL si crece.
    logs_by_session: dict[str, dict[str, list[WorkoutSetLog]]] = defaultdict(lambda: defaultdict(list))
    all_logs: list[WorkoutSetLog] = []
    if all_sessions:
        for log in db.scalars(select(WorkoutSetLog).where(WorkoutSetLog.session_id.in_([s.id for s, _ in all_sessions]))):
            logs_by_session[log.session_id][log.exercise_id].append(log)
            all_logs.append(log)
    exercise_info = {
        ex.id: ex
        for ex in db.scalars(select(Exercise).where(Exercise.id.in_({log.exercise_id for log in all_logs})))
    }

    def group_of(exercise_id: str) -> str:
        info = exercise_info.get(exercise_id)
        return info.target_muscle_group if info else NO_GROUP

    muscle_groups = sorted({group_of(log.exercise_id) for log in all_logs})
    log_ids = {log.id: log for log in all_logs}
    pr_keys = {
        (log_ids[row].session_id, log_ids[row].exercise_id)
        for row in db.scalars(
            select(PersonalRecord.workout_set_log_id).where(PersonalRecord.workout_set_log_id.in_(log_ids))
        )
    }
    feedback = {
        row.session_id: row.comment or row.category
        for row in db.scalars(select(EffortFeedback).where(EffortFeedback.relationship_id == relationship.id))
    }

    planned_cache: dict[tuple[str, str], list[dict]] = {}

    def planned(session: WorkoutSession) -> list[dict]:
        key = (session.routine_id, session.day_name)
        if key not in planned_cache:
            planned_cache[key] = _planned_entries(db, session.routine_id, session.day_name)
        return planned_cache[key]

    # ---- ¿Está progresando? ----
    per_exercise: dict[str, list[tuple[WorkoutSession, datetime, Best]]] = defaultdict(list)
    for session, finished in sessions:
        for exercise_id, logs in logs_by_session.get(session.id, {}).items():
            best = _best(logs)
            if best is not None:
                per_exercise[exercise_id].append((session, finished, best))
    exercises: list[ExerciseProgress] = []
    for exercise_id in {eid for s, _ in sessions for eid in logs_by_session.get(s.id, {})}:
        entries = per_exercise.get(exercise_id, [])
        info = exercise_info.get(exercise_id)
        name = info.name if info else exercise_id
        group = group_of(exercise_id)
        if not entries:
            exercises.append(ExerciseProgress(
                exercise_id=exercise_id, name=name, muscle_group=group, metric="none", status="no_metric", points=[]
            ))
            continue
        kind = "max_weight" if any(best[0] > 0 for *_, best in entries) else "max_reps"
        history = [(f.date(), best) for _, f, best in entries if _monday(f.date()) < current_monday]
        status, improved_on = classify(history, kind, current_monday)
        shown = [(f.date(), best) for _, f, best in entries] if status == "few_data" else history
        start, current = shown[0][1], shown[-1][1]
        start_main = _main(start, kind)
        change = round((_main(current, kind) - start_main) / start_main * 100, 1) if status != "few_data" and start_main > 0 else None
        improved_session = next((s for s, f, _ in entries if f.date() == improved_on), None) if improved_on else None

        buckets: dict[date, list[tuple[WorkoutSession, datetime, Best]]] = defaultdict(list)
        for entry in entries:
            buckets[entry[1].date() if group_by == "session" else _monday(entry[1].date())].append(entry)
        points = []
        for key_day, items in sorted(buckets.items()):
            for session, finished, best in ([max(items, key=lambda item: item[2])] if group_by == "week" else items):
                day = finished.date()
                monday = _monday(day)
                target = next((p["target_weight_kg"] for p in planned(session) if p["exercise_id"] == exercise_id), None)
                points.append(ExercisePoint(
                    key=session.id if group_by == "session" else monday.isoformat(),
                    period_start=day if group_by == "session" else monday,
                    period_end=day if group_by == "session" else monday + timedelta(days=6),
                    weight=best[0] if best[0] > 0 else None,
                    reps=best[1],
                    target_weight=float(target) if target is not None else None,
                    rpe=session.rpe,
                    is_pr=(session.id, exercise_id) in pr_keys if group_by == "session" else any((s.id, exercise_id) in pr_keys for s, _, _ in items),
                    is_partial=monday == current_monday,
                ))
        exercises.append(ExerciseProgress(
            exercise_id=exercise_id, name=name, muscle_group=group, metric=kind,
            start=_result(start), current=_result(current), change_pct=change,
            last_improvement=LastImprovement(date=improved_on, is_pr=(improved_session.id, exercise_id) in pr_keys)
            if improved_session else None,
            status=status, points=points,
        ))
    order = {"declined": 0, "stalled": 1, "progressing": 2, "unchanged": 3, "few_data": 4, "no_metric": 5}
    exercises.sort(key=lambda item: (order[item.status], item.name))
    rated = [item for item in exercises if item.status in ("progressing", "stalled", "declined", "unchanged")]
    improving = sum(1 for item in rated if item.status == "progressing")
    progress_pct = improving / len(rated) * 100 if rated else None
    progress = ProgressSummary(
        improving=improving, with_data=len(rated),
        status=_light(progress_pct, PROGRESS_GREEN_PCT, PROGRESS_YELLOW_PCT) if progress_pct is not None else None,
    )

    # ---- ¿Está entrenando lo que le programé? ----
    weekly, assigned_at, _ = _weekly_trainings(db, relationship, now.replace(tzinfo=None))
    first_week = _monday(_as_utc(assigned_at).date() if assigned_at else relationship.start_date)
    if range_start is not None:
        first_week = max(first_week, range_start)
    done_by_week: dict[date, int] = defaultdict(int)
    for _, finished in all_sessions:
        done_by_week[_monday(finished.date())] += 1
    adherence: list[AdherenceWeek] = []
    week = first_week
    while range_start is not None and weekly > 0 and week <= current_monday:
        adherence.append(AdherenceWeek(
            period_start=week, period_end=week + timedelta(days=6), scheduled=weekly,
            completed=done_by_week.get(week, 0), is_partial=week == current_monday,
        ))
        week += timedelta(weeks=1)
    full_weeks = [item for item in adherence if not item.is_partial]
    scheduled_total = sum(item.scheduled for item in full_weeks)
    completed_total = sum(min(item.completed, item.scheduled) for item in full_weeks)
    adherence_pct = round(completed_total / scheduled_total * 100) if scheduled_total else None

    planned_sets = done_sets = 0
    per_planned: dict[str, dict] = {}
    for session, _ in complete:
        replacements = _replacements(db, session)
        logs = logs_by_session.get(session.id, {})
        for entry in planned(session):
            original = entry["exercise_id"]
            performed = original if original in logs else replacements.get(original, original)
            done = min(len(logs.get(performed, [])), entry["sets"])
            planned_sets += entry["sets"]
            done_sets += done
            row = per_planned.setdefault(original, {"planned": 0, "done": 0, "skips": 0, "replaced": False})
            row["planned"] += entry["sets"]
            row["done"] += done
            if done == 0:
                row["skips"] += 1
                row["replaced"] = row["replaced"] or original in replacements
    sets_pct = round(done_sets / planned_sets * 100) if planned_sets else None
    names = {ex.id: ex.name for ex in db.scalars(select(Exercise).where(Exercise.id.in_(per_planned.keys())))}
    most_skipped = sorted(
        (
            MostSkipped(
                exercise_id=key, name=names.get(key, key), completion_pct=round(row["done"] / row["planned"] * 100),
                skip_count=row["skips"], main_reason="replacement_requested" if row["replaced"] else None,
            )
            for key, row in per_planned.items()
            if row["planned"] and row["done"] / row["planned"] * 100 < SKIPPED_BELOW_PCT
        ),
        key=lambda item: (item.completion_pct, item.name),
    )[:MOST_SKIPPED_LIMIT]
    adherence_summary = AdherenceSummary(
        completed_sessions=completed_total, scheduled_sessions=scheduled_total, pct=adherence_pct,
        sets_completion_pct=sets_pct,
        status=_light(adherence_pct, ADHERENCE_GREEN_PCT, ADHERENCE_YELLOW_PCT) if adherence_pct is not None else None,
    )

    # ---- ¿Cómo le está costando? ----
    rpe_points: list[RpePoint] = []
    if group_by == "session":
        for session, finished in sessions:
            day = finished.date()
            rpe_points.append(RpePoint(
                key=session.id, period_start=day, period_end=day, rpe=session.rpe, has_report=session.rpe is not None,
                trainer_feedback=feedback.get(session.id), is_partial=_monday(day) == current_monday,
            ))
    else:
        weekly_rpe: dict[date, list[int | None]] = defaultdict(list)
        for session, finished in sessions:
            weekly_rpe[_monday(finished.date())].append(session.rpe)
        for monday, values in sorted(weekly_rpe.items()):
            rated_values = [v for v in values if v is not None]
            rpe_points.append(RpePoint(
                key=monday.isoformat(), period_start=monday, period_end=monday + timedelta(days=6),
                rpe=round(sum(rated_values) / len(rated_values), 1) if rated_values else None,
                has_report=bool(rated_values), is_partial=monday == current_monday,
            ))
    reported = [s.rpe for s, _ in complete if s.rpe is not None]
    last_rpe, previous_rpe = reported[-RPE_WINDOW:], reported[-2 * RPE_WINDOW:-RPE_WINDOW]
    avg_rpe = round(sum(last_rpe) / len(last_rpe), 1) if last_rpe else None
    trend = None
    if avg_rpe is not None:
        gap = sum(last_rpe) / len(last_rpe) - sum(previous_rpe) / len(previous_rpe) if previous_rpe else 0
        trend = "rising" if gap > RPE_TREND_TOLERANCE else "falling" if gap < -RPE_TREND_TOLERANCE else "stable"
    load_up = progress.status == "green"
    excessive = any(s.rpe is not None and s.rpe >= RPE_EXCESSIVE for s, _ in sessions)
    message = effort_message(excessive, load_up, trend, avg_rpe)
    effort_status = None
    if avg_rpe is not None:
        effort_status = (
            "red" if avg_rpe >= RPE_EXCESSIVE or message == "fatigue"
            else "yellow" if avg_rpe < RPE_LOW or avg_rpe > RPE_HIGH or message == "excessive_effort"
            else "green"
        )

    # ---- ¿Qué tengo que ajustar? ----
    review: list[ReviewItem] = []
    for item in exercises:
        if item.status == "declined":
            drop = abs(item.change_pct) if item.change_pct is not None else None
            review.append(ReviewItem(
                type="exercise_declined", exercise_id=item.exercise_id,
                label=f"{item.name} bajó{f' {drop:.0f} %' if drop else ''}",
            ))
    review += [
        ReviewItem(type="exercise_stalled", exercise_id=i.exercise_id, label=f"{i.name} sin mejora en las últimas {STATUS_WINDOW_WEEKS} semanas")
        for i in exercises if i.status == "stalled"
    ]
    if message in ("fatigue", "excessive_effort"):
        review.append(ReviewItem(
            type=message,
            label="El esfuerzo sube sin mejora de carga: posible fatiga" if message == "fatigue"
            else "Hubo sesiones con esfuerzo excesivo",
        ))
    review += [
        ReviewItem(type="exercise_skipped", exercise_id=i.exercise_id, label=f"{i.name} se completó al {i.completion_pct} %")
        for i in most_skipped
    ]
    review += [
        ReviewItem(type="week_without_training", label=f"Sin entrenar la semana del {w.period_start.day}/{w.period_start.month}")
        for w in full_weeks[-2:] if w.completed == 0
    ]

    # ---- Series semanales por grupo muscular ----
    weeks_count = len(full_weeks)
    done_by_group: dict[str, int] = defaultdict(int)
    for session, _ in complete:
        for exercise_id, logs in logs_by_session.get(session.id, {}).items():
            done_by_group[group_of(exercise_id)] += len(logs)
    planned_week = [
        entry
        for routine_id, days in _routine_days(db, relationship)
        for day_name in days
        for entry in _planned_entries(db, routine_id, day_name)
    ]
    missing = {entry["exercise_id"] for entry in planned_week} - exercise_info.keys()
    if missing:
        exercise_info.update({ex.id: ex for ex in db.scalars(select(Exercise).where(Exercise.id.in_(missing)))})
    scheduled_by_group: dict[str, int] = defaultdict(int)  # cada día de la rutina una vez por semana
    for entry in planned_week:
        scheduled_by_group[group_of(entry["exercise_id"])] += entry["sets"]
    muscle_groups = sorted({*muscle_groups, *scheduled_by_group})
    sets_by_group = sorted(
        (
            MuscleGroupSets(
                muscle_group=group,
                avg_completed_per_week=round(done_by_group.get(group, 0) / weeks_count, 1),
                avg_scheduled_per_week=float(scheduled_by_group.get(group, 0)),
            )
            for group in {*done_by_group, *scheduled_by_group}
            if weeks_count
        ),
        key=lambda item: (-item.avg_completed_per_week, item.muscle_group),
    )

    if muscle_group:
        exercises = [item for item in exercises if item.muscle_group == muscle_group]
        sets_by_group = [item for item in sets_by_group if item.muscle_group == muscle_group]
    return TrainingEvolution(
        period=EvolutionPeriod(key=period, start=range_start, end=today),
        group_by=group_by,
        muscle_group=muscle_group,
        muscle_groups=muscle_groups,
        has_sessions=bool(all_sessions),
        summary=EvolutionSummary(
            progress=progress,
            adherence=adherence_summary,
            effort=EffortSummary(avg_rpe_last_4=avg_rpe, trend=trend, message_key=message, status=effort_status),
            to_review=ReviewSummary(
                count=len(review),
                status="green" if not review else "yellow" if len(review) <= REVIEW_YELLOW_MAX else "red",
            ),
        ),
        exercises=exercises,
        adherence=adherence,
        most_skipped=most_skipped,
        rpe=rpe_points,
        sets_by_muscle_group=sets_by_group,
        to_review=review,
    )


def _routine_days(db: Session, relationship: TrainingRelationship) -> list[tuple[str, list[str]]]:
    """(id de rutina, nombres de día) de la rutina vigente del alumno."""
    student_routine = db.scalar(
        select(StudentRoutine).where(
            StudentRoutine.relationship_id == relationship.id, StudentRoutine.status != "UNASSIGNED"
        )
    )
    if student_routine is not None:
        return [(student_routine.id, [day["name"] for day in student_routine.days or []])]
    if not relationship.initial_routine_id:
        return []
    source = db.get(RoutineTemplate, relationship.initial_routine_id) or db.get(AssignedRoutine, relationship.initial_routine_id)
    return [(source.id, [day.name for day in source.days])] if source else []
