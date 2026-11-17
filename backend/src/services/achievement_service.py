"""Logros y medallas del alumno (US-67).

Catálogo fijo del MVP. Cada hito se mide sobre los datos existentes (sesiones finalizadas,
récords personales y racha) y se guarda con la fecha real en que se alcanzó. Los hitos que ya
estaban cumplidos antes de la funcionalidad se otorgan en silencio (retroactivos).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.models.achievement import AchievementCongratulation, StudentAchievement
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.achievement import (
    AchievementItem,
    AchievementsOverview,
    CongratulationView,
    LockedAchievement,
)
from backend.src.services.notification_service import create_notification
from backend.src.services.streak_service import (
    monday,
    relationship_week_data,
    streak_reached_on,
    student_routine_relationship,
)
from backend.src.services.trainer_student_service import (
    TrainerStudentError,
    _active_relationship,
    _trainer_profile,
)

logger = logging.getLogger(__name__)

ACHIEVEMENT_UNLOCKED = "ACHIEVEMENT_UNLOCKED"
CONGRATULATION = "CONGRATULATION"
ONLY_STUDENTS = "Esta acción está disponible solo para alumnos."
NOT_FOUND = "No se encontró el logro."
ALREADY_CONGRATULATED = "Ya felicitaste a este alumno por este logro."


@dataclass(frozen=True)
class Definition:
    code: str
    title: str
    description: str
    target: int
    metric: str  # "sessions" | "records" | "streak"


CATALOG: tuple[Definition, ...] = (
    Definition("FIRST_SESSION", "Primera sesión", "Completaste tu primera sesión de entrenamiento.", 1, "sessions"),
    Definition("TEN_SESSIONS", "10 sesiones", "Completaste 10 sesiones de entrenamiento.", 10, "sessions"),
    Definition("STREAK_4_WEEKS", "Racha de 4 semanas", "Cumpliste tu objetivo semanal 4 semanas seguidas.", 4, "streak"),
    Definition("FIRST_PR", "Primer récord personal", "Superaste tu mejor peso en un ejercicio por primera vez.", 1, "records"),
    Definition("FIVE_PRS", "5 récords personales", "Lograste 5 récords personales.", 5, "records"),
)
BY_CODE = {item.code: item for item in CATALOG}


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AchievementError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _session_dates(db: Session, profile: StudentProfile) -> list[datetime]:
    """Fin de cada sesión finalizada del alumno (todos sus vínculos), en orden."""
    rows = db.scalars(
        select(WorkoutSession.finished_at)
        .where(WorkoutSession.student_id == profile.id, WorkoutSession.finished_at.is_not(None))
        .order_by(WorkoutSession.finished_at)
    )
    return [_naive(value) for value in rows]


def _record_dates(db: Session, profile: StudentProfile) -> list[datetime]:
    """Momento de cada récord: un peso que supera estrictamente el máximo previo del ejercicio (US-65)."""
    logs = db.scalars(
        select(WorkoutSetLog)
        .where(WorkoutSetLog.student_id == profile.id, WorkoutSetLog.weight_kg > 0)
        .order_by(WorkoutSetLog.recorded_at, WorkoutSetLog.set_number)
    )
    best: dict[str, float] = {}
    dates: list[datetime] = []
    for log in logs:
        weight = float(log.weight_kg)
        if log.exercise_id not in best or weight > best[log.exercise_id]:
            best[log.exercise_id] = weight
            dates.append(_naive(log.recorded_at))
    return dates


def _streak_unlock(db: Session, profile: StudentProfile, weeks: int) -> datetime | None:
    relationship = student_routine_relationship(db, profile)
    data = relationship_week_data(db, relationship) if relationship else None
    if data is None:
        return None
    weekly, first_week, done_by_week = data
    reached = streak_reached_on(weekly, first_week, done_by_week, monday(utc_now().date()), weeks)
    return datetime.combine(reached, time.min) if reached else None


@dataclass(frozen=True)
class Progress:
    """Avance del alumno hacia cada hito."""

    sessions: list[datetime]
    records: list[datetime]
    streak_weeks: int


def _progress(db: Session, profile: StudentProfile) -> Progress:
    from backend.src.services.streak_service import _relationship_streak

    relationship = student_routine_relationship(db, profile)
    weeks = _relationship_streak(db, relationship)[0].max_weeks if relationship else 0
    return Progress(_session_dates(db, profile), _record_dates(db, profile), weeks)


def _unlock_date(definition: Definition, progress: Progress, db: Session, profile: StudentProfile) -> datetime | None:
    if definition.metric == "sessions":
        return progress.sessions[definition.target - 1] if len(progress.sessions) >= definition.target else None
    if definition.metric == "records":
        return progress.records[definition.target - 1] if len(progress.records) >= definition.target else None
    return _streak_unlock(db, profile, definition.target)


def evaluate_achievements(
    db: Session, profile: StudentProfile, trigger_session: WorkoutSession | None = None
) -> list[StudentAchievement]:
    """Otorga los logros alcanzados y devuelve los nuevos.

    Es "nuevo" (celebra y notifica) el hito que alcanzó la sesión que acaba de finalizar o la racha
    que se completó esta semana; el resto estaba cumplido de antes y se otorga en silencio.
    """
    existing = set(db.scalars(select(StudentAchievement.code).where(StudentAchievement.student_id == profile.id)))
    pending = [item for item in CATALOG if item.code not in existing]
    if not pending:
        return []
    progress = _progress(db, profile)
    now = utc_now()
    this_monday = datetime.combine(monday(now.date()), time.min)
    started = _naive(trigger_session.started_at) if trigger_session is not None else None
    created: list[StudentAchievement] = []
    for definition in pending:
        unlocked_at = _unlock_date(definition, progress, db, profile)
        if unlocked_at is None:
            continue
        fresh = (started is not None and unlocked_at >= started) or (
            definition.metric == "streak" and unlocked_at >= this_monday
        )
        achievement = StudentAchievement(
            student_id=profile.id,
            code=definition.code,
            unlocked_at=unlocked_at,
            retroactive=not fresh,
            celebrated_at=None if fresh else now,
            created_at=now,
        )
        db.add(achievement)
        created.append(achievement)
    db.flush()
    for achievement in created:
        if not achievement.retroactive:
            _notify_unlocked(db, profile, achievement)
    return created


def _notify_unlocked(db: Session, profile: StudentProfile, achievement: StudentAchievement) -> None:
    definition = BY_CODE[achievement.code]
    student_user = db.get(User, profile.user_id)
    name = " ".join(part for part in (profile.first_name, profile.last_name) if part).strip() or student_user.email
    create_notification(
        db,
        recipient_id=student_user.id,
        type=ACHIEVEMENT_UNLOCKED,
        title=f"¡Desbloqueaste un logro: {definition.title}!",
        message=definition.description,
        related_entity_type="StudentAchievement",
        related_entity_id=achievement.id,
    )
    trainer_ids = db.scalars(
        select(TrainingRelationship.trainer_id).where(
            TrainingRelationship.student_id == profile.id, TrainingRelationship.status == "ACTIVE"
        )
    )
    for trainer_id in set(trainer_ids):
        trainer = db.get(TrainerProfile, trainer_id)
        create_notification(
            db,
            recipient_id=trainer.user_id,
            type=ACHIEVEMENT_UNLOCKED,
            title=f"{name} desbloqueó un logro: {definition.title}",
            message="Podés felicitarlo desde el detalle del alumno.",
            related_entity_type="StudentAchievement",
            related_entity_id=achievement.id,
            related_student_id=profile.id,
        )


def evaluate_after_session(db: Session, session: WorkoutSession) -> None:
    """Gancho del cierre de sesión: un error de logros nunca debe impedir finalizar el entrenamiento."""
    try:
        profile = db.get(StudentProfile, session.student_id)
        if profile is not None and evaluate_achievements(db, profile, session):
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        logger.exception("No se pudieron evaluar los logros de la sesión %s", session.id)


def _congratulation_view(db: Session, congratulation: AchievementCongratulation | None) -> CongratulationView | None:
    if congratulation is None:
        return None
    trainer = db.get(TrainerProfile, congratulation.trainer_id)
    trainer_user = db.get(User, trainer.user_id) if trainer else None
    name = ((trainer.full_name or "").strip() if trainer else "") or (trainer_user.email if trainer_user else "")
    return CongratulationView(
        message=congratulation.message,
        trainer_name=name,
        created_at=congratulation.created_at,
        seen_at=congratulation.seen_at,
    )


def _items(db: Session, achievements: list[StudentAchievement]) -> list[AchievementItem]:
    ids = [item.id for item in achievements]
    congratulations = {}
    if ids:
        congratulations = {
            c.achievement_id: c
            for c in db.scalars(select(AchievementCongratulation).where(AchievementCongratulation.achievement_id.in_(ids)))
        }
    result = []
    for achievement in sorted(achievements, key=lambda item: item.unlocked_at, reverse=True):
        definition = BY_CODE[achievement.code]
        result.append(
            AchievementItem(
                id=achievement.id,
                code=achievement.code,
                title=definition.title,
                description=definition.description,
                unlocked_at=achievement.unlocked_at,
                retroactive=achievement.retroactive,
                pending_celebration=achievement.celebrated_at is None,
                congratulation=_congratulation_view(db, congratulations.get(achievement.id)),
            )
        )
    return result


def _locked(progress: Progress, unlocked_codes: set[str]) -> list[LockedAchievement]:
    current = {"sessions": len(progress.sessions), "records": len(progress.records), "streak": progress.streak_weeks}
    return [
        LockedAchievement(
            code=item.code,
            title=item.title,
            description=item.description,
            current=min(current[item.metric], item.target),
            target=item.target,
        )
        for item in CATALOG
        if item.code not in unlocked_codes
    ]


def _overview(db: Session, profile: StudentProfile) -> AchievementsOverview:
    achievements = list(db.scalars(select(StudentAchievement).where(StudentAchievement.student_id == profile.id)))
    progress = _progress(db, profile)
    return AchievementsOverview(
        unlocked=_items(db, achievements),
        locked=_locked(progress, {item.code for item in achievements}),
    )


def get_student_achievements(db: Session, user: User) -> AchievementsOverview:
    """Escenario 3: logros con su fecha y avance de los que faltan (evalúa los pendientes, p. ej. la racha)."""
    if user.role != STUDENT_ROLE:
        raise AchievementError(403, ONLY_STUDENTS)
    profile = user.student_profile
    if profile is None:
        return AchievementsOverview(unlocked=[], locked=_locked(Progress([], [], 0), set()))
    if evaluate_achievements(db, profile):
        db.commit()
    return _overview(db, profile)


def mark_celebrated(db: Session, user: User, achievement_id: str) -> None:
    """Escenario 2: el alumno cerró la celebración."""
    achievement = _own_achievement(db, user, achievement_id)
    if achievement.celebrated_at is None:
        achievement.celebrated_at = utc_now()
        db.commit()


def _own_achievement(db: Session, user: User, achievement_id: str) -> StudentAchievement:
    if user.role != STUDENT_ROLE:
        raise AchievementError(403, ONLY_STUDENTS)
    achievement = db.get(StudentAchievement, achievement_id)
    if achievement is None or user.student_profile is None or achievement.student_id != user.student_profile.id:
        raise AchievementError(404, NOT_FOUND)
    return achievement


def mark_congratulation_seen(db: Session, user: User, achievement_id: str) -> None:
    """Escenario 4: el alumno vio la felicitación (se muestra una sola vez)."""
    achievement = _own_achievement(db, user, achievement_id)
    congratulation = db.scalar(
        select(AchievementCongratulation).where(AchievementCongratulation.achievement_id == achievement.id)
    )
    if congratulation is None:
        raise AchievementError(404, NOT_FOUND)
    if congratulation.seen_at is None:
        congratulation.seen_at = utc_now()
        db.commit()


def get_trainer_student_achievements(db: Session, user: User, student_id: str) -> AchievementsOverview:
    """El entrenador ve los logros de su alumno activo y puede felicitarlo."""
    trainer = _trainer_profile(db, user)
    _active_relationship(db, trainer.id, student_id)
    return _overview(db, db.get(StudentProfile, student_id))


def congratulate(db: Session, user: User, achievement_id: str, message: str) -> AchievementItem:
    """Escenario 4: felicitación del entrenador (una por logro) que el alumno ve en su próxima sesión."""
    if user.role != TRAINER_ROLE:
        raise TrainerStudentError(403, "Esta acción está disponible solo para entrenadores.")
    trainer = _trainer_profile(db, user)
    achievement = db.get(StudentAchievement, achievement_id)
    if achievement is None:
        raise AchievementError(404, NOT_FOUND)
    _active_relationship(db, trainer.id, achievement.student_id)  # 404 si no es su alumno activo
    if db.scalar(select(AchievementCongratulation.id).where(AchievementCongratulation.achievement_id == achievement.id)):
        raise AchievementError(409, ALREADY_CONGRATULATED)
    congratulation = AchievementCongratulation(
        achievement_id=achievement.id, trainer_id=trainer.id, message=message, created_at=utc_now()
    )
    db.add(congratulation)
    profile = db.get(StudentProfile, achievement.student_id)
    definition = BY_CODE[achievement.code]
    trainer_name = (trainer.full_name or "").strip() or user.email
    create_notification(
        db,
        recipient_id=profile.user_id,
        type=CONGRATULATION,
        title=f"{trainer_name} te felicitó por tu logro: {definition.title}",
        message="La vas a ver al abrir tu próxima sesión de entrenamiento.",
        related_entity_type="StudentAchievement",
        related_entity_id=achievement.id,
    )
    db.commit()
    return _items(db, [achievement])[0]
