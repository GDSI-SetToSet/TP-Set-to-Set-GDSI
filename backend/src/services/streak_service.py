"""Racha de constancia de entrenamiento (US-68).

La racha se calcula a partir de las sesiones finalizadas; no se guarda. El objetivo semanal son
los días de la rutina vigente (criterio de US-30 y US-32). Semanas de lunes a domingo en UTC,
desde la asignación de la rutina; la semana en curso solo suma o corta cuando termina.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
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
    weekly_target: int, first_week: date, done_by_week: dict[date, int], current_monday: date
) -> StreakResult:
    """Cálculo puro. Una semana terminada se cumple con al menos `weekly_target` sesiones finalizadas."""
    this_week = done_by_week.get(current_monday, 0)
    if weekly_target <= 0:
        return StreakResult(0, 0, this_week, None)
    results: list[bool] = []
    week = monday(first_week)
    while week < current_monday:
        results.append(done_by_week.get(week, 0) >= weekly_target)
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
    weekly_target: int, first_week: date, done_by_week: dict[date, int], current_monday: date, weeks: int
) -> date | None:
    """US-67: día en que la racha llegó por primera vez a `weeks` semanas (lunes que sigue a la última cumplida)."""
    if weekly_target <= 0 or weeks <= 0:
        return None
    run = 0
    week = monday(first_week)
    while week < current_monday:
        run = run + 1 if done_by_week.get(week, 0) >= weekly_target else 0
        if run >= weeks:
            return week + timedelta(weeks=1)
        week += timedelta(weeks=1)
    return None


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def relationship_week_data(
    db: Session, relationship: TrainingRelationship
) -> tuple[int, date, dict[date, int]] | None:
    """Objetivo semanal, primera semana y sesiones finalizadas por semana; None sin rutina asignada."""
    now = _now()
    weekly, assigned_at, _ = _weekly_trainings(db, relationship, now)
    if weekly <= 0:
        return None
    first_week = monday(assigned_at.date() if assigned_at else relationship.start_date)
    done_by_week: dict[date, int] = defaultdict(int)
    finished = db.scalars(
        select(WorkoutSession.finished_at).where(
            WorkoutSession.relationship_id == relationship.id,
            WorkoutSession.finished_at.is_not(None),
        )
    )
    for finished_at in finished:
        moment = finished_at.astimezone(UTC).replace(tzinfo=None) if finished_at.tzinfo else finished_at
        done_by_week[monday(moment.date())] += 1
    return weekly, first_week, done_by_week


def _relationship_streak(db: Session, relationship: TrainingRelationship) -> tuple[TrainingStreak, StreakResult | None]:
    current_monday = monday(_now().date())
    data = relationship_week_data(db, relationship)
    if data is None:
        empty = TrainingStreak(
            has_routine=False, weekly_target=0, current_weeks=0, max_weeks=0,
            this_week_sessions=0, week_start=current_monday,
        )
        return empty, None
    weekly, first_week, done_by_week = data
    result = compute_streak(weekly, first_week, done_by_week, current_monday)
    view = TrainingStreak(
        has_routine=True,
        weekly_target=weekly,
        current_weeks=result.current_weeks,
        max_weeks=result.max_weeks,
        this_week_sessions=result.this_week_sessions,
        week_start=current_monday,
    )
    return view, result


def student_routine_relationship(db: Session, profile: StudentProfile) -> TrainingRelationship | None:
    """Vínculo activo con rutina asignada (el alumno entrena una rutina a la vez)."""
    relationships = db.scalars(
        select(TrainingRelationship)
        .where(TrainingRelationship.student_id == profile.id, TrainingRelationship.status == "ACTIVE")
        .order_by(TrainingRelationship.start_date.desc())
    )
    now = _now()
    for relationship in relationships:
        if _weekly_trainings(db, relationship, now)[0] > 0:
            return relationship
    return None


def _notify_reset(db: Session, user: User, broken_week: date) -> None:
    """Escenario 2: un solo mensaje de aliento por racha cortada."""
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
    create_notification(
        db,
        recipient_id=user.id,
        type=STREAK_RESET,
        title="Tu racha se reinició, ¡arrancá una nueva!",
        message="La semana pasada no llegaste a las sesiones de tu rutina. Esta semana es una nueva oportunidad: cada sesión cuenta.",
        related_entity_type="TrainingStreak",
        related_entity_id=key,
        commit=True,
    )


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
