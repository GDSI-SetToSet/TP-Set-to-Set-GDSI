from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import VALIDATION_ERROR_MESSAGE
from backend.src.models.exercise import Exercise
from backend.src.models.routine_template import (
    RoutineTemplate,
    RoutineTemplateBlock,
    RoutineTemplateBlockEstimate,
    RoutineTemplateDay,
    RoutineTemplateExercise,
    RoutineTemplateExercisePrescription,
)
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.routine_template import RoutineTemplateInput
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.trainer_service import (
    get_or_create_profile as get_trainer_profile,
)
from backend.src.services.trainer_service import utc_now

# Literal: el nombre de la constante cambió entre versiones de Starlette.
VALIDATION_ERROR_STATUS = 422
EXERCISE_UNAVAILABLE_MESSAGE = "El ejercicio no está disponible en tu biblioteca"


class RoutineTemplateError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def own_template_exercise_ids(template: RoutineTemplate) -> set[str]:
    return {entry.exercise_id for day in template.days for block in day.blocks for entry in block.exercises}


# Un ejercicio dado de baja solo se admite si la rutina ya lo incluía (spec 005, casos borde).
def validate_exercises(
    db: Session, profile: TrainerProfile, payload: RoutineTemplateInput, retained_ids: set[str]
) -> None:
    entries = [
        (f"days.{day_index}.blocks.{block_index}.exercises.{entry_index}.exercise_id", entry.exercise_id)
        for day_index, day in enumerate(payload.days)
        for block_index, block in enumerate(day.blocks)
        for entry_index, entry in enumerate(block.exercises)
    ]
    query = select(Exercise).where(
        Exercise.id.in_({exercise_id for _, exercise_id in entries}), Exercise.trainer_id == profile.id
    )
    exercises = {exercise.id: exercise for exercise in db.scalars(query)}

    errors: list[dict[str, str]] = []
    for field, exercise_id in entries:
        exercise = exercises.get(exercise_id)
        if exercise is None or (exercise.deleted_at is not None and exercise_id not in retained_ids):
            errors.append({"field": field, "message": EXERCISE_UNAVAILABLE_MESSAGE})
        elif payload.has_no_materials_alternative and not exercise.has_no_materials_alternative:
            errors.append({"field": field, "message": f'"{exercise.name}" no tiene alternativa "Sin materiales"'})
    if errors:
        raise RoutineTemplateError(VALIDATION_ERROR_STATUS, VALIDATION_ERROR_MESSAGE, errors)


def build_days(payload: RoutineTemplateInput) -> list[RoutineTemplateDay]:
    return [
        RoutineTemplateDay(
            order_index=day_index,
            name=day.name,
            blocks=[
                RoutineTemplateBlock(
                    order_index=block_index,
                    name=block.name,
                    estimate=(
                        RoutineTemplateBlockEstimate(
                            estimated_duration_minutes=block.estimated_duration_minutes
                        )
                        if block.estimated_duration_minutes is not None
                        else None
                    ),
                    exercises=[
                        RoutineTemplateExercise(
                            order_index=entry_index,
                            exercise_id=entry.exercise_id,
                            sets=entry.sets,
                            reps=entry.reps,
                            rest_seconds=entry.rest_seconds,
                            prescription=RoutineTemplateExercisePrescription(
                                target_weight_kg=entry.target_weight_kg
                            ),
                        )
                        for entry_index, entry in enumerate(block.exercises)
                    ],
                )
                for block_index, block in enumerate(day.blocks)
            ],
        )
        for day_index, day in enumerate(payload.days)
    ]


def list_own_templates(db: Session, user: User) -> list[RoutineTemplate]:
    profile = get_trainer_profile(db, user)
    query = select(RoutineTemplate).where(RoutineTemplate.trainer_id == profile.id)
    return list(db.scalars(query.order_by(RoutineTemplate.name)))


def create_template(db: Session, user: User, payload: RoutineTemplateInput) -> RoutineTemplate:
    profile = get_trainer_profile(db, user)
    validate_exercises(db, profile, payload, retained_ids=set())
    now = utc_now()
    template = RoutineTemplate(
        trainer_id=profile.id,
        name=payload.name,
        duration_weeks=payload.duration_weeks,
        intensity=payload.intensity,
        has_no_materials_alternative=payload.has_no_materials_alternative,
        days=build_days(payload),
        created_at=now,
        updated_at=now,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_own_template(db: Session, user: User, template_id: str) -> RoutineTemplate:
    profile = get_trainer_profile(db, user)
    template = db.get(RoutineTemplate, template_id)
    if template is None or template.trainer_id != profile.id:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "Rutina no encontrada.")
    return template


def update_template(db: Session, user: User, template_id: str, payload: RoutineTemplateInput) -> RoutineTemplate:
    template = get_own_template(db, user, template_id)
    validate_exercises(db, template.trainer, payload, retained_ids=own_template_exercise_ids(template))
    template.name = payload.name
    template.duration_weeks = payload.duration_weeks
    template.intensity = payload.intensity
    template.has_no_materials_alternative = payload.has_no_materials_alternative
    template.days = build_days(payload)
    template.updated_at = utc_now()
    db.commit()
    db.refresh(template)
    return template


def active_trainer_ids(student_profile_id: str):
    return select(TrainingRelationship.trainer_id).where(
        TrainingRelationship.student_id == student_profile_id,
        TrainingRelationship.status == "ACTIVE",
    )


# El vínculo activo se valida en cada petición: al terminarlo, el alumno pierde el acceso (Principio III).
def list_student_templates(db: Session, user: User) -> list[RoutineTemplate]:
    profile = get_student_profile(db, user)
    query = select(RoutineTemplate).where(RoutineTemplate.trainer_id.in_(active_trainer_ids(profile.id)))
    return list(db.scalars(query.order_by(RoutineTemplate.name)))


def get_student_template(db: Session, user: User, template_id: str) -> RoutineTemplate:
    profile = get_student_profile(db, user)
    template = db.scalar(
        select(RoutineTemplate).where(
            RoutineTemplate.id == template_id, RoutineTemplate.trainer_id.in_(active_trainer_ids(profile.id))
        )
    )
    if template is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "Rutina no encontrada.")
    return template


def get_assigned_student_template(db: Session, user: User) -> RoutineTemplate | None:
    profile = get_student_profile(db, user)
    relationship = db.scalar(
        select(TrainingRelationship)
        .where(
            TrainingRelationship.student_id == profile.id,
            TrainingRelationship.status == "ACTIVE",
            TrainingRelationship.initial_routine_id.is_not(None),
        )
        .order_by(TrainingRelationship.start_date.desc())
    )
    if relationship is None or relationship.initial_routine_id is None:
        return None
    return db.scalar(
        select(RoutineTemplate).where(
            RoutineTemplate.id == relationship.initial_routine_id,
            RoutineTemplate.trainer_id == relationship.trainer_id,
        )
    )


def list_routine_assignments(db: Session, user: User) -> list[dict[str, str | None]]:
    trainer = get_trainer_profile(db, user)
    rows = db.execute(
        select(TrainingRelationship, StudentProfile, User)
        .join(StudentProfile, TrainingRelationship.student_id == StudentProfile.id)
        .join(User, StudentProfile.user_id == User.id)
        .where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
        .order_by(StudentProfile.last_name, StudentProfile.first_name)
    ).all()

    assignments: list[dict[str, str | None]] = []
    for relationship, student, student_user in rows:
        routine = None
        if relationship.initial_routine_id:
            routine = db.scalar(
                select(RoutineTemplate).where(
                    RoutineTemplate.id == relationship.initial_routine_id,
                    RoutineTemplate.trainer_id == trainer.id,
                )
            )
        student_name = " ".join(part for part in (student.first_name, student.last_name) if part).strip()
        assignments.append(
            {
                "relationship_id": relationship.id,
                "student_id": student.id,
                "student_name": student_name or student_user.email,
                "routine_template_id": routine.id if routine else None,
                "routine_name": routine.name if routine else None,
            }
        )
    return assignments


def assign_routine_to_student(
    db: Session, user: User, relationship_id: str, routine_template_id: str | None
) -> dict[str, str | None]:
    trainer = get_trainer_profile(db, user)
    relationship = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.id == relationship_id,
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if relationship is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No se encontró un vínculo activo con ese alumno.")

    if routine_template_id is not None:
        routine = db.scalar(
            select(RoutineTemplate).where(
                RoutineTemplate.id == routine_template_id,
                RoutineTemplate.trainer_id == trainer.id,
            )
        )
        if routine is None:
            raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "Rutina no encontrada.")

    relationship.initial_routine_id = routine_template_id
    db.commit()
    return {"relationship_id": relationship.id, "routine_template_id": routine_template_id}
