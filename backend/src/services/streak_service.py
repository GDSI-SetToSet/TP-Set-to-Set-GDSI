"""Racha de constancia de entrenamiento (US-68).

La racha se calcula a partir de las sesiones finalizadas; no se guarda. El objetivo semanal son
los días de la rutina vigente (criterio de US-30 y US-32). Semanas de lunes a domingo en UTC,
desde la asignación de la rutina; la semana en curso solo suma o corta cuando termina.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE
from backend.src.models.notification import Notification
from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.schemas.student_progress import TrainingStreak
from backend.src.services.abandonment_risk_service import _weekly_trainings
from backend.src.services.notification_service import create_notification
from backend.src.services.trainer_student_service import (
    TrainerStudentError,
    _active_relationship,
    _trainer_profile,
)

STREAK_RESET = "STREAK_RESET"


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass(frozen=True)
class StreakResult:
    current_weeks: int
    max_weeks: int
    this_week_sessions: int
    # Lunes de la última semana terminada si esa semana cortó una racha de al menos una semana.
    broken_week: date | None


def compute_streak(
    weekly_target: int,
    first_week: date,
    done_by_week: dict[date, int],
    current_monday: date,
    weekly_targets: dict[date, int] | None = None,
) -> StreakResult:
    """Cálculo puro. Una semana terminada se cumple con al menos el objetivo semanal de esa semana."""
    this_week = done_by_week.get(current_monday, 0)
    if weekly_target <= 0:
        return StreakResult(0, 0, this_week, None)
    results: list[bool] = []
    week = monday(first_week)
    while week < current_monday:
        target = weekly_targets.get(week, weekly_target) if weekly_targets else weekly_target
        results.append(target > 0 and done_by_week.get(week, 0) >= target)
        week += timedelta(weeks=1)

    longest = run = 0
    for met in results:
        run = run + 1 if met else 0
        longest = max(longest, run)
    current = run  # la serie que termina en la última semana terminada
    broken = None
    if len(results) >= 2 and not results[-1] and results[-2]:
        broken = current_monday - timedelta(weeks=1)
    return StreakResult(current, longest, this_week, broken)


def streak_reached_on(
    weekly_target: int,
    first_week: date,
    done_by_week: dict[date, int],
    current_monday: date,
    weeks: int,
    weekly_targets: dict[date, int] | None = None,
) -> date | None:
    """US-67: día en que la racha llegó por primera vez a `weeks` semanas (lunes que sigue a la última cumplida)."""
    if weekly_target <= 0 or weeks <= 0:
        return None
    run = 0
    week = monday(first_week)
    while week < current_monday:
        target = weekly_targets.get(week, weekly_target) if weekly_targets else weekly_target
        run = run + 1 if (target > 0 and done_by_week.get(week, 0) >= target) else 0
        if run >= weeks:
            return week + timedelta(weeks=1)
        week += timedelta(weeks=1)
    return None


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def relationship_week_data(
    db: Session, relationship: TrainingRelationship, now: datetime | None = None
) -> tuple[int, date, dict[date, int], dict[date, int]] | None:
    """Objetivo semanal, primera semana, sesiones finalizadas y objetivo por semana; None sin rutina."""
    resolved_now = now or _now()
    weekly, assigned_at, _ = _weekly_trainings(db, relationship, resolved_now)
    if weekly <= 0:
        return None
    done_by_week: dict[date, int] = defaultdict(int)
    raw_week_targets: dict[date, int] = {}
    earliest_session_date: date | None = None
    finished_rows = db.execute(
        select(WorkoutSession.finished_at, WorkoutSession.weekly_target)
        .where(
            WorkoutSession.relationship_id == relationship.id,
            WorkoutSession.finished_at.is_not(None),
        )
        .order_by(WorkoutSession.finished_at)
    ).all()
    for finished_at, session_target in finished_rows:
        moment = finished_at.astimezone(UTC).replace(tzinfo=None) if finished_at.tzinfo else finished_at
        session_day = moment.date()
        if earliest_session_date is None or session_day < earliest_session_date:
            earliest_session_date = session_day
        week = monday(session_day)
        done_by_week[week] += 1
        if session_target is not None and session_target > 0:
            raw_week_targets[week] = session_target

    assigned_day = assigned_at.date() if assigned_at else relationship.start_date
    anchor_day = min(assigned_day, earliest_session_date) if earliest_session_date is not None else assigned_day
    first_week = monday(anchor_day)
    assigned_week = monday(assigned_day)

    week_targets: dict[date, int] = {}
    last_known_target: int | None = None
    cur_week = first_week
    current_monday = monday(resolved_now.date())
    while cur_week <= current_monday:
        if cur_week in raw_week_targets:
            week_targets[cur_week] = raw_week_targets[cur_week]
            last_known_target = raw_week_targets[cur_week]
        elif cur_week < assigned_week and last_known_target is not None:
            week_targets[cur_week] = last_known_target
        else:
            week_targets[cur_week] = weekly
        cur_week += timedelta(weeks=1)

    return weekly, first_week, done_by_week, week_targets


def _relationship_streak(
    db: Session, relationship: TrainingRelationship, now: datetime | None = None
) -> tuple[TrainingStreak, StreakResult | None]:
    resolved_now = now or _now()
    current_monday = monday(resolved_now.date())
    data = relationship_week_data(db, relationship, now=resolved_now)
    if data is None:
        empty = TrainingStreak(
            has_routine=False, weekly_target=0, current_weeks=0, max_weeks=0,
            this_week_sessions=0, week_start=current_monday,
        )
        return empty, None
    weekly, first_week, done_by_week, week_targets = data
    result = compute_streak(weekly, first_week, done_by_week, current_monday, weekly_targets=week_targets)
    view = TrainingStreak(
        has_routine=True,
        weekly_target=weekly,
        current_weeks=result.current_weeks,
        max_weeks=result.max_weeks,
        this_week_sessions=result.this_week_sessions,
        week_start=current_monday,
    )
    return view, result


def student_routine_relationship(
    db: Session, profile: StudentProfile, now: datetime | None = None
) -> TrainingRelationship | None:
    """Vínculo activo con rutina asignada (el alumno entrena una rutina a la vez)."""
    relationships = db.scalars(
        select(TrainingRelationship)
        .where(TrainingRelationship.student_id == profile.id, TrainingRelationship.status == "ACTIVE")
        .order_by(TrainingRelationship.start_date.desc())
    )
    resolved_now = now or _now()
    for relationship in relationships:
        if _weekly_trainings(db, relationship, resolved_now)[0] > 0:
            return relationship
    return None


def _notify_reset(db: Session, user: User, broken_week: date) -> None:
    """Escenario 2: un solo mensaje de aliento por racha cortada (protegido contra carreras)."""
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    key = broken_week.isoformat()
    exists = db.scalar(
        select(Notification.id).where(
            Notification.recipient_id == user.id,
            Notification.type == STREAK_RESET,
            Notification.related_entity_id == key,
        )
    )
    if exists is not None:
        return
    try:
        with db.begin_nested():
            create_notification(
                db,
                recipient_id=user.id,
                type=STREAK_RESET,
                title="Tu racha se reinició, ¡arrancá una nueva!",
                message="La semana pasada no llegaste a las sesiones de tu rutina. Esta semana es una nueva oportunidad: cada sesión cuenta.",
                related_entity_type="TrainingStreak",
                related_entity_id=key,
                commit=False,
            )
            db.flush()
    except IntegrityError:
        return
    db.commit()


def get_student_streak(db: Session, user: User) -> TrainingStreak:
    """Escenarios 1, 2 y 4: racha del alumno autenticado."""
    if user.role != STUDENT_ROLE:
        raise TrainerStudentError(403, "Esta acción está disponible solo para alumnos.")
    current_monday = monday(_now().date())
    profile = user.student_profile
    relationship = student_routine_relationship(db, profile) if profile else None
    if relationship is None:
        return TrainingStreak(
            has_routine=False, weekly_target=0, current_weeks=0, max_weeks=0,
            this_week_sessions=0, week_start=current_monday,
        )
    view, result = _relationship_streak(db, relationship)
    if result is not None and result.broken_week is not None:
        _notify_reset(db, user, result.broken_week)
    return view


def get_trainer_student_streak(db: Session, user: User, student_id: str) -> TrainingStreak:
    """Escenario 3: el entrenador ve la racha de su alumno activo."""
    trainer = _trainer_profile(db, user)
    relationship = _active_relationship(db, trainer.id, student_id)
    return _relationship_streak(db, relationship)[0]
