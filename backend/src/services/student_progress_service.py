"""US-65: "Mi evolución" del alumno. Informa y motiva; no diagnostica (eso es la vista del entrenador, US-30).

Todo se deriva de las series registradas del propio alumno; no hay tablas nuevas. Reutiliza `classify` y
`adherence_weeks` de `training_evolution_service`: acá solo cambia el mensaje (`message_key`).
- Récord: mejor serie del día que supera la mejor anterior del ejercicio (más peso, o mismo peso con más
  repeticiones). La primera carga de un ejercicio no es récord. Se recalcula: `PersonalRecord` guarda solo el máximo.
- La semana en curso queda fuera de estados y constancia.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.exercise import Exercise
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.student_progress import (
    ExerciseEvolution,
    ExercisePoint,
    NewExercise,
    NextExercise,
    NextSession,
    ProgressPeriod,
    ProgressSummary,
    RecordEntry,
    StreakSummary,
    StudentProgress,
)
from backend.src.services import routine_template_service
from backend.src.services.daily_routine_tracking_service import _as_utc
from backend.src.services.effort_feedback_service import (
    CATEGORY_LABELS,
    list_student_effort_feedback,
)
from backend.src.services.session_adjustment_service import list_student_adjustments
from backend.src.services.session_comparison_service import _planned_entries
from backend.src.services.student_service import get_or_create_profile
from backend.src.services.training_evolution_service import (
    NO_GROUP,
    PERIOD_WEEKS,
    Best,
    _best,
    _main,
    _monday,
    _result,
    _routine_days,
    adherence_weeks,
    classify,
)

IMPROVING_WEEKS = 4  # "mejorando": al menos una mejora en las últimas 4 semanas completas
IMPROVED = ("weight_increased", "reps_increased", "bodyweight_reps_increased")


def _streak(full_weeks: list) -> StreakSummary:
    best = run = 0
    for week in full_weeks:
        run = run + 1 if week.completed >= week.scheduled else 0
        best = max(best, run)
    return StreakSummary(current_weeks=run, best_weeks=best)  # `run` al final = racha que llega a la última semana completa


def _message_key(status: str, kind: str, start: Best, current: Best) -> str:
    if status == "few_data":
        return "few_data"
    if status == "declined":
        return "below_best"
    if status == "progressing":
        if kind == "max_reps" and current[1] > start[1]:
            return "bodyweight_reps_increased"
        if kind == "max_weight" and current[0] > start[0]:
            return "weight_increased"
        if kind == "max_weight" and current[0] == start[0] and current[1] > start[1]:
            return "reps_increased"
    return "no_change"


def _next_session(db: Session, user: User, relationship: TrainingRelationship | None, last_best: dict[str, Best]) -> NextSession | None:
    """Próximo día de la rutina vigente, en ciclo, después del último día finalizado. La app no calcula cargas."""
    if relationship is None:
        return None
    routines = _routine_days(db, relationship)
    if not routines or not routines[0][1]:
        return None
    routine_id, days = routines[0]
    last = db.scalar(
        select(WorkoutSession)
        .where(WorkoutSession.relationship_id == relationship.id, WorkoutSession.finished_at.is_not(None))
        .order_by(WorkoutSession.finished_at.desc())
    )
    day_name = days[(days.index(last.day_name) + 1) % len(days)] if last and last.day_name in days else days[0]
    entries = _planned_entries(db, routine_id, day_name)
    names = {ex.id: ex.name for ex in db.scalars(select(Exercise).where(Exercise.id.in_({e["exercise_id"] for e in entries})))}
    notice = next((n for n in list_student_adjustments(db, user) if n.day_name == day_name), None)
    feedback = next(iter(list_student_effort_feedback(db, user)), None)
    return NextSession(
        day_name=day_name,
        trainer_feedback=(feedback["comment"] or CATEGORY_LABELS[feedback["category"]]) if feedback else None,
        exercises=[
            NextExercise(
                exercise_id=e["exercise_id"], name=names.get(e["exercise_id"], e["exercise_id"]),
                last=_result(last_best[e["exercise_id"]]) if e["exercise_id"] in last_best else None,
                target_weight=float(e["target_weight_kg"]) if e["target_weight_kg"] is not None else None,
                reps=str(e["reps"]), sets=e["sets"],
                adjusted_by_trainer=bool(notice and e["exercise_id"] in notice.exercise_ids),
                trainer_note=notice.note if notice and e["exercise_id"] in notice.exercise_ids else None,
            )
            for e in entries
        ],
    )


def get_student_progress(
    db: Session, user: User, period: Literal["4w", "12w", "all"] = "12w", muscle_group: str | None = None
) -> StudentProgress:
    profile = get_or_create_profile(db, user)  # solo datos propios; 403 si no es alumno
    now = _as_utc(routine_template_service.utc_now())
    today = now.date()
    current_monday = _monday(today)
    range_start = current_monday - timedelta(weeks=PERIOD_WEEKS[period] - 1) if period in PERIOD_WEEKS else None

    # ponytail: se leen todas las series del alumno; agregar en SQL si el historial crece (SC-001).
    logs = list(
        db.scalars(
            select(WorkoutSetLog).where(WorkoutSetLog.student_id == profile.id).order_by(WorkoutSetLog.recorded_at, WorkoutSetLog.set_number)
        )
    )
    by_day: dict[str, dict[date, list[WorkoutSetLog]]] = defaultdict(lambda: defaultdict(list))
    for log in logs:
        by_day[log.exercise_id][_as_utc(log.recorded_at).date()].append(log)
    info = {ex.id: ex for ex in db.scalars(select(Exercise).where(Exercise.id.in_(by_day)))}
    group_of = lambda eid: info[eid].target_muscle_group if eid in info else NO_GROUP

    # Mejor serie por ejercicio y día (sobre todo el historial); los días sin métrica numérica se descartan.
    history: dict[str, list[tuple[date, Best]]] = {}
    for eid, days in by_day.items():
        rows = [(day, best) for day, day_logs in sorted(days.items()) if (best := _best(day_logs)) is not None]
        if rows:
            history[eid] = rows

    # Récords y primera fecha, sobre todo el historial: la marca previa no depende del período.
    record_days: dict[str, dict[date, Best]] = defaultdict(dict)  # eid -> día -> marca anterior
    for eid, rows in history.items():
        top = rows[0][1]
        for day, best in rows[1:]:
            if best > top:
                record_days[eid][day] = top
                top = best

    in_period = lambda day: range_start is None or day >= range_start
    records = sorted(
        (
            RecordEntry(
                date=day, exercise_id=eid, name=info[eid].name if eid in info else eid,
                weight=best[0] or None, reps=best[1], previous=_result(previous),
            )
            for eid, days in record_days.items()
            for day, previous in days.items()
            if in_period(day) and (best := dict(history[eid])[day])
        ),
        key=lambda r: (r.date, r.name), reverse=True,
    )

    exercises: list[ExerciseEvolution] = []
    improving = 0
    for eid, rows in history.items():
        complete = [(d, b) for d, b in rows if _monday(d) < current_monday]
        full_kind = "max_weight" if any(b[0] > 0 for _, b in rows) else "max_reps"
        _, improved_on = classify(complete, full_kind, current_monday)
        if improved_on and improved_on >= current_monday - timedelta(weeks=IMPROVING_WEEKS):
            improving += 1  # resumen: sobre todo el historial y sin filtro de grupo
        period_rows = [(d, b) for d, b in rows if in_period(d)]
        if not period_rows:
            continue
        kind = "max_weight" if any(b[0] > 0 for _, b in period_rows) else "max_reps"
        hist = [(d, b) for d, b in period_rows if _monday(d) < current_monday]
        status, improved_on = classify(hist, kind, current_monday)
        shown = period_rows if status == "few_data" else hist
        start, current = shown[0][1], shown[-1][1]
        targets: dict[date, float | None] = {}
        for day, day_logs in by_day[eid].items():
            if in_period(day):
                planned = _planned_entries(db, day_logs[0].routine_id, day_logs[0].day_name)
                target = next((p["target_weight_kg"] for p in planned if p["exercise_id"] == eid), None)
                targets[day] = float(target) if target is not None else None
        exercises.append(ExerciseEvolution(
            exercise_id=eid, name=info[eid].name if eid in info else by_day[eid][period_rows[0][0]][0].exercise_name,
            muscle_group=group_of(eid), metric=kind, start=_result(start), current=_result(current),
            best=_result(max((b for _, b in period_rows), key=lambda b: (_main(b, kind), b))),
            message_key=_message_key(status, kind, start, current),
            weeks_without_change=max(0, (today - (improved_on or shown[0][0])).days // 7),
            last_improvement_is_pr=improved_on in record_days.get(eid, {}) if improved_on else False,
            points=[
                ExercisePoint(date=d, weight=b[0] or None, reps=b[1], target_weight=targets.get(d), is_pr=d in record_days.get(eid, {}))
                for d, b in period_rows
            ],
        ))
    muscle_groups = sorted({e.muscle_group for e in exercises})
    streak_weeks: list = []
    relationship = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.student_id == profile.id, TrainingRelationship.status == "ACTIVE"
        )
    )
    consistency = []
    if relationship is not None:
        finished = [
            _as_utc(s.finished_at).date()
            for s in db.scalars(select(WorkoutSession).where(WorkoutSession.student_id == profile.id, WorkoutSession.finished_at.is_not(None)))
        ]
        all_weeks = adherence_weeks(db, relationship, now, finished, date.min)
        streak_weeks = [w for w in all_weeks if not w.is_partial]
        consistency = [w for w in all_weeks if range_start is None or w.period_start >= range_start]

    summary = ProgressSummary(improving_exercises_last_4w=improving, streak=_streak(streak_weeks), records_in_period=len(records))
    new_exercises = sorted(
        (
            NewExercise(exercise_id=e.exercise_id, name=e.name, first_date=history[e.exercise_id][0][0])
            for e in exercises
            if in_period(history[e.exercise_id][0][0])
        ),
        key=lambda n: (n.first_date, n.name),
    )
    next_session = _next_session(db, user, relationship, {eid: rows[-1][1] for eid, rows in history.items()})

    if muscle_group:
        exercises = [e for e in exercises if e.muscle_group == muscle_group]
        keep = {e.exercise_id for e in exercises}
        records = [r for r in records if r.exercise_id in keep]
        new_exercises = [n for n in new_exercises if n.exercise_id in keep]
    exercises.sort(key=lambda e: (e.message_key not in IMPROVED, e.name))
    return StudentProgress(
        period=ProgressPeriod(
            key=period, end=today,
            start=range_start or (min((rows[0][0] for rows in history.values()), default=None)),
        ),
        muscle_group=muscle_group, muscle_groups=muscle_groups, has_sessions=bool(history),
        summary=summary, exercises=exercises, consistency=consistency, records=records,
        new_exercises=new_exercises, next_session=next_session,
    )
