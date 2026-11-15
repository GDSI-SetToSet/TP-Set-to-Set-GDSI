"""US-65: evolución de cargas, volumen semanal y récords personales del alumno.

Todo se deriva de las series registradas (`WorkoutSetLog`) del propio alumno; no hay tablas nuevas.
- PR (FR-001a): serie con peso > 0 que supera ESTRICTAMENTE el máximo previo del ejercicio (sin importar reps).
- Volumen (FR-001b): Σ(kg × reps) de series con peso > 0 y repeticiones numéricas.
"""

from collections import defaultdict
from datetime import date, timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.exercise import Exercise
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSetLog
from backend.src.schemas.student_progress import (
    ExerciseLoad,
    LoadPoint,
    PersonalRecordEntry,
    ProgressRange,
    StudentProgress,
    WeekComparison,
    WeeklyVolume,
)
from backend.src.services import routine_template_service
from backend.src.services.daily_routine_tracking_service import _as_utc
from backend.src.services.session_comparison_service import _number
from backend.src.services.student_service import (
    StudentProfileError,
    get_or_create_profile,
)

DEFAULT_WEEKS = 12  # FR-001c
NO_GROUP = "Sin grupo"


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _day(log: WorkoutSetLog) -> date:
    return _as_utc(log.recorded_at).date()


def _reps(log: WorkoutSetLog) -> float:
    value = _number(log.reps_completed)
    return float(value) if value is not None else 0.0


def get_student_progress(
    db: Session,
    user: User,
    exercise_id: str | None = None,
    muscle_group: str | None = None,
    from_: date | None = None,
    to: date | None = None,
) -> StudentProgress:
    profile = get_or_create_profile(db, user)  # solo datos propios; 403 si no es alumno
    today = _as_utc(routine_template_service.utc_now()).date()
    is_default = from_ is None and to is None
    end = to or today
    start = from_ or _monday(end) - timedelta(weeks=DEFAULT_WEEKS - 1)
    if start > end:
        raise StudentProfileError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La fecha inicial no puede ser posterior a la final.",
            errors=[{"field": "from", "message": "Debe ser anterior o igual a 'to'."}],
        )

    # ponytail: se leen todas las series del alumno; agregar en SQL si el historial crece (SC-001).
    logs = list(
        db.scalars(
            select(WorkoutSetLog)
            .where(WorkoutSetLog.student_id == profile.id, WorkoutSetLog.weight_kg > 0)
            .order_by(WorkoutSetLog.recorded_at, WorkoutSetLog.set_number)
        )
    )
    exercises = {ex.id: ex for ex in db.scalars(select(Exercise).where(Exercise.id.in_({log.exercise_id for log in logs})))}

    def group_of(eid: str) -> str:
        return exercises[eid].target_muscle_group if eid in exercises else NO_GROUP

    def name_of(log: WorkoutSetLog) -> str:
        return exercises[log.exercise_id].name if log.exercise_id in exercises else log.exercise_name

    # PRs sobre todo el historial: el máximo previo no depende del rango ni de los filtros.
    running: dict[str, float] = {}
    pr_info: dict[str, float | None] = {}  # id de serie -> peso previo (None = PR inicial)
    for log in logs:
        weight = float(log.weight_kg)
        if log.exercise_id not in running or weight > running[log.exercise_id]:
            pr_info[log.id] = running.get(log.exercise_id)
            running[log.exercise_id] = weight

    shown = [
        log
        for log in logs
        if start <= _day(log) <= end
        and (exercise_id is None or log.exercise_id == exercise_id)
        and (muscle_group is None or group_of(log.exercise_id) == muscle_group)
    ]

    # Carga por ejercicio: mejor serie de cada día (más peso; a igual peso, más repeticiones).
    by_day: dict[str, dict[date, list[WorkoutSetLog]]] = defaultdict(lambda: defaultdict(list))
    for log in shown:
        by_day[log.exercise_id][_day(log)].append(log)
    loads = []
    for eid, days in by_day.items():
        points = []
        for day, day_logs in sorted(days.items()):
            best = max(day_logs, key=lambda log: (float(log.weight_kg), _reps(log)))
            points.append(LoadPoint(
                date=day, weight_kg=float(best.weight_kg), reps=best.reps_completed,
                is_pr=any(log.id in pr_info for log in day_logs),
            ))
        loads.append(ExerciseLoad(
            exercise_id=eid, name=name_of(day_logs[0]), muscle_group=group_of(eid),
            has_trend=len(points) >= 2, points=points,
        ))
    loads.sort(key=lambda item: (-len(item.points), item.name))

    # Volumen semanal: una entrada por semana del rango, 0 si no hubo series.
    volume: dict[date, float] = defaultdict(float)
    for log in shown:
        reps = _number(log.reps_completed)
        if reps is not None:
            volume[_monday(_day(log))] += float(log.weight_kg) * float(reps)
    current_monday = _monday(today)
    weekly = []
    week = _monday(start)
    while week <= _monday(end):
        weekly.append(WeeklyVolume(
            week_start=week, week_end=week + timedelta(days=6),
            volume_kg=round(volume.get(week, 0.0), 2), is_partial=week == current_monday,
        ))
        week += timedelta(weeks=1)
    current = weekly[-1].volume_kg
    earlier = [item.volume_kg for item in weekly[:-1]]
    previous = earlier[-1] if earlier else 0.0
    comparison = WeekComparison(
        current_volume_kg=current, previous_volume_kg=previous,
        delta_vs_previous_pct=round((current - previous) / previous * 100, 1) if previous > 0 else None,
        previous_avg_kg=round(sum(earlier) / len(earlier), 2) if earlier else 0.0,
    )

    records = [
        PersonalRecordEntry(
            exercise_id=log.exercise_id, exercise_name=name_of(log), weight_kg=float(log.weight_kg),
            reps=log.reps_completed, achieved_at=_as_utc(log.recorded_at),
            previous_weight_kg=pr_info[log.id], is_initial=pr_info[log.id] is None,
        )
        for log in shown
        if log.id in pr_info
    ]  # `shown` ya está en orden cronológico ascendente

    return StudentProgress(
        range=ProgressRange(from_=start, to=end, is_default=is_default),
        muscle_groups=sorted({group_of(log.exercise_id) for log in logs}),
        has_data=bool(shown),
        exercises=loads,
        weekly_volume=weekly,
        week_comparison=comparison,
        personal_records=records,
    )
