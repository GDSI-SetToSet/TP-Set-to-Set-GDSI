from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.src.models.exercise import Exercise
from backend.src.models.user import User
from backend.src.schemas.exercise import ExerciseInput
from backend.src.services.trainer_service import get_or_create_profile, utc_now


class ExerciseError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def list_own_exercises(db: Session, user: User, muscle_group: str | None = None) -> list[Exercise]:
    profile = get_or_create_profile(db, user)
    query = select(Exercise).where(Exercise.trainer_id == profile.id, Exercise.deleted_at.is_(None))
    if muscle_group and muscle_group.strip():
        query = query.where(func.lower(Exercise.target_muscle_group) == muscle_group.strip().lower())
    return list(db.scalars(query.order_by(Exercise.name)))


def create_exercise(db: Session, user: User, payload: ExerciseInput) -> Exercise:
    profile = get_or_create_profile(db, user)
    now = utc_now()
    exercise = Exercise(trainer_id=profile.id, **payload.model_dump(), created_at=now, updated_at=now)
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def get_own_exercise(db: Session, user: User, exercise_id: str) -> Exercise:
    profile = get_or_create_profile(db, user)
    exercise = db.get(Exercise, exercise_id)
    if exercise is None or exercise.trainer_id != profile.id or exercise.deleted_at is not None:
        raise ExerciseError(status.HTTP_404_NOT_FOUND, "Ejercicio no encontrado.")
    return exercise


def update_exercise(db: Session, user: User, exercise_id: str, payload: ExerciseInput) -> Exercise:
    exercise = get_own_exercise(db, user, exercise_id)
    for field, value in payload.model_dump().items():
        setattr(exercise, field, value)
    exercise.updated_at = utc_now()
    db.commit()
    db.refresh(exercise)
    return exercise


# Baja lógica: las rutinas que ya incluyen el ejercicio lo conservan (spec 005, casos borde).
def delete_exercise(db: Session, user: User, exercise_id: str) -> None:
    exercise = get_own_exercise(db, user, exercise_id)
    exercise.deleted_at = utc_now()
    db.commit()
