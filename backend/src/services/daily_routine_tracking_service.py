"""US-22: seguimiento de las rutinas del día de los alumnos activos del entrenador."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.trainer_student import (
    DailyRoutineExercise,
    DailyRoutineItem,
    DailyRoutineSession,
    DailyRoutineSet,
)
from backend.src.services.routine_template_service import (
    RoutineTemplateError,
    list_routine_assignments,
)
from backend.src.services.trainer_service import (
    TrainerProfileError,
    get_or_create_profile,
)
from backend.src.services.trainer_student_service import TrainerStudentError

STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_TRAINING = "TRAINING"
STATUS_FINISHED = "FINISHED"
MAX_UTC_OFFSET_MINUTES = 14 * 60


def _as_utc(value: datetime) -> datetime:
    """Los timestamps se guardan en UTC sin zona; se exponen con zona explícita."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def day_window(day: date, utc_offset_minutes: int) -> tuple[datetime, datetime]:
    """Límites UTC (naive, como se persisten) del día local del entrenador."""
    if abs(utc_offset_minutes) > MAX_UTC_OFFSET_MINUTES:
        raise TrainerStudentError(422, "El desfase horario indicado no es válido.")
    local_start = datetime(day.year, day.month, day.day)
    start = local_start - timedelta(minutes=utc_offset_minutes)
    return start, start + timedelta(days=1)


def _pick_session(sessions: list[WorkoutSession]) -> WorkoutSession | None:
    """Prioriza una sesión en curso; si no hay, la última finalizada del día."""
    in_progress = [session for session in sessions if session.finished_at is None]
    candidates = in_progress or sessions
    return max(candidates, key=lambda session: session.started_at, default=None)


def _group_exercises(logs: list[WorkoutSetLog]) -> list[DailyRoutineExercise]:
    grouped: dict[str, list[WorkoutSetLog]] = defaultdict(list)
    for log in sorted(logs, key=lambda item: (item.recorded_at, item.set_number)):
        grouped[log.exercise_id].append(log)
    return [
        DailyRoutineExercise(
            exercise_id=exercise_id,
            exercise_name=items[0].exercise_name,
            sets=[
                DailyRoutineSet(
                    set_number=log.set_number,
                    reps_completed=log.reps_completed,
                    weight_kg=float(log.weight_kg) if log.weight_kg is not None else None,
                    duration_seconds=log.duration_seconds,
                    recorded_at=_as_utc(log.recorded_at),
                )
                for log in sorted(items, key=lambda item: item.set_number)
            ],
        )
        for exercise_id, items in grouped.items()
    ]


def list_daily_routines(
    db: Session, user: User, day: date, utc_offset_minutes: int = 0
) -> list[DailyRoutineItem]:
    try:
        trainer = get_or_create_profile(db, user)
        assignments = list_routine_assignments(db, user)
    except (TrainerProfileError, RoutineTemplateError) as error:
        raise TrainerStudentError(error.status_code, error.detail) from error
    if not assignments:
        return []

    start, end = day_window(day, utc_offset_minutes)
    relationship_ids = [str(item["relationship_id"]) for item in assignments]
    owned_ids = set(
        db.scalars(
            select(TrainingRelationship.id).where(
                TrainingRelationship.id.in_(relationship_ids),
                TrainingRelationship.trainer_id == trainer.id,
                TrainingRelationship.status == "ACTIVE",
            )
        )
    )

    sessions_by_relationship: dict[str, list[WorkoutSession]] = defaultdict(list)
    for session in db.scalars(
        select(WorkoutSession).where(
            WorkoutSession.relationship_id.in_(owned_ids),
            WorkoutSession.started_at >= start,
            WorkoutSession.started_at < end,
        )
    ):
        sessions_by_relationship[session.relationship_id].append(session)

    chosen = {
        relationship_id: session
        for relationship_id, sessions in sessions_by_relationship.items()
        if (session := _pick_session(sessions)) is not None
    }

    logs_by_relationship: dict[str, list[WorkoutSetLog]] = defaultdict(list)
    chosen_session_ids = [session.id for session in chosen.values()]
    if chosen_session_ids:
        for log in db.scalars(
            select(WorkoutSetLog).where(
                or_(
                    WorkoutSetLog.session_id.in_(chosen_session_ids),
                    and_(
                        WorkoutSetLog.session_id.is_(None),
                        WorkoutSetLog.relationship_id.in_(list(chosen)),
                        WorkoutSetLog.recorded_at >= start,
                        WorkoutSetLog.recorded_at < end,
                    ),
                )
            )
        ):
            session = chosen.get(log.relationship_id)
            if session is not None and (log.session_id in (None, session.id)):
                logs_by_relationship[log.relationship_id].append(log)

    items: list[DailyRoutineItem] = []
    for assignment in assignments:
        relationship_id = str(assignment["relationship_id"])
        if relationship_id not in owned_ids:
            continue
        session = chosen.get(relationship_id)
        status = STATUS_NOT_STARTED
        session_view = None
        exercises: list[DailyRoutineExercise] = []
        if session is not None:
            status = STATUS_TRAINING if session.finished_at is None else STATUS_FINISHED
            duration = (
                int((session.finished_at - session.started_at).total_seconds())
                if session.finished_at is not None
                else None
            )
            session_view = DailyRoutineSession(
                id=session.id,
                day_name=session.day_name,
                modality=session.modality,
                started_at=_as_utc(session.started_at),
                finished_at=_as_utc(session.finished_at) if session.finished_at else None,
                duration_seconds=duration,
                rpe=session.rpe,
            )
            exercises = _group_exercises(logs_by_relationship.get(relationship_id, []))
        items.append(
            DailyRoutineItem(
                relationship_id=relationship_id,
                student_id=str(assignment["student_id"]),
                student_name=str(assignment["student_name"]),
                routine_name=assignment["routine_name"],
                status=status,
                session=session_view,
                exercises=exercises,
            )
        )
    return items
