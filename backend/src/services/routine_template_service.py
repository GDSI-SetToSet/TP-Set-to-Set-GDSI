from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import VALIDATION_ERROR_MESSAGE
from backend.src.models.assigned_routine import AssignedRoutine
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
from backend.src.models.student_routine import StudentRoutine
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.schemas.routine_template import (
    RoutineModalityUpdate,
    RoutineTemplateInput,
    WorkoutSessionStartInput,
    WorkoutSetLogInput,
)
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


def delete_template(db: Session, user: User, template_id: str) -> None:
    from backend.src.services.student_routine_service import preserve_student_copies

    template = get_own_template(db, user, template_id)
    preserve_student_copies(db, template.trainer_id, template.id)
    db.delete(template)
    db.commit()


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


def _routine_supports_home(routine: RoutineTemplate | AssignedRoutine) -> bool:
    return all(
        entry.exercise.has_no_materials_alternative
        for day in routine.days
        for block in day.blocks
        for entry in block.exercises
    )


def _resolve_from_initial_routine(
    db: Session, relationship: TrainingRelationship
) -> RoutineTemplate | dict | None:
    if relationship.initial_routine_id is None:
        return None
    template = db.scalar(
        select(RoutineTemplate).where(
            RoutineTemplate.id == relationship.initial_routine_id,
            RoutineTemplate.trainer_id == relationship.trainer_id,
        )
    )
    if template is not None:
        effective_modality = relationship.routine_modality or "GYM"
        if effective_modality == "HOME" and not _routine_supports_home(template):
            effective_modality = "GYM"
            relationship.routine_modality = "GYM"
            db.commit()
        template._modality = effective_modality
        return template

    # Si initial_routine_id corresponde a una AssignedRoutine aprobada, renderizar vista
    assigned = db.scalar(
        select(AssignedRoutine).where(
            AssignedRoutine.id == relationship.initial_routine_id,
            AssignedRoutine.trainer_id == relationship.trainer_id,
            AssignedRoutine.status == "APPROVED",
        )
    )
    if assigned is not None:
        from backend.src.services.student_routine_service import ensure_routine, render

        sr = ensure_routine(db, relationship)
        return render(db, sr)
    return None


def get_assigned_student_template(db: Session, user: User) -> RoutineTemplate | dict | None:
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
    if relationship is None:
        return None
    return _resolve_from_initial_routine(db, relationship)


def _resolve_student_active_routine(
    db: Session, user: User
) -> tuple[TrainingRelationship, RoutineTemplate | dict]:
    from backend.src.services.student_routine_service import render

    profile = get_student_profile(db, user)
    routine = db.scalar(
        select(StudentRoutine)
        .join(TrainingRelationship, StudentRoutine.relationship_id == TrainingRelationship.id)
        .where(
            TrainingRelationship.student_id == profile.id,
            TrainingRelationship.status == "ACTIVE",
            StudentRoutine.status != "UNASSIGNED",
        )
    )
    if routine is not None:
        relationship = db.get(TrainingRelationship, routine.relationship_id)
        return relationship, render(db, routine)

    relationship = db.scalar(
        select(TrainingRelationship)
        .where(
            TrainingRelationship.student_id == profile.id,
            TrainingRelationship.status == "ACTIVE",
            TrainingRelationship.initial_routine_id.is_not(None),
        )
        .order_by(TrainingRelationship.start_date.desc())
    )
    if relationship is not None:
        resolved = _resolve_from_initial_routine(db, relationship)
        if resolved is not None:
            return relationship, resolved

    raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No tenés una rutina activa asignada.")


def _iter_routine_exercises(routine_view: RoutineTemplate | dict):
    is_template = isinstance(routine_view, RoutineTemplate)
    days = routine_view.days if is_template else routine_view["days"]
    for day_index, day in enumerate(days):
        day_name = day.name if is_template else day["name"]
        blocks = day.blocks if is_template else day["blocks"]
        for block_index, block in enumerate(blocks):
            exercises = block.exercises if is_template else block["exercises"]
            for entry_index, entry in enumerate(exercises):
                ex: Exercise = entry.exercise if is_template else entry["exercise"]
                yield day_index, day_name, block_index, entry_index, ex


def update_student_routine_modality(
    db: Session, user: User, payload: RoutineModalityUpdate
) -> RoutineTemplate | dict:
    relationship, routine_view = _resolve_student_active_routine(db, user)
    target_modality = payload.modality

    if target_modality == "HOME":
        errors: list[dict[str, str]] = []
        blocking_names: list[str] = []
        for day_index, day_name, block_index, entry_index, ex in _iter_routine_exercises(routine_view):
            if not ex.has_no_materials_alternative:
                field = f"days.{day_index}.blocks.{block_index}.exercises.{entry_index}.exercise_id"
                errors.append(
                    {
                        "field": field,
                        "message": (
                            f'"{ex.name}" ({day_name}) no tiene alternativa "Sin materiales" cargada '
                            f"(requiere equipamiento: {ex.equipment_needed})."
                        ),
                    }
                )
                if ex.name not in blocking_names:
                    blocking_names.append(ex.name)

        if errors:
            joined_names = ", ".join(f'"{name}"' for name in blocking_names)
            if len(blocking_names) == 1:
                detail = (
                    f"No se puede alternar a la modalidad Casa/Viaje porque el ejercicio {joined_names} "
                    'no tiene una alternativa "Sin materiales" cargada.'
                )
            else:
                detail = (
                    f"No se puede alternar a la modalidad Casa/Viaje porque los ejercicios {joined_names} "
                    'no tienen una alternativa "Sin materiales" cargada.'
                )
            raise RoutineTemplateError(VALIDATION_ERROR_STATUS, detail, errors)

    relationship.routine_modality = target_modality
    db.commit()
    if isinstance(routine_view, RoutineTemplate):
        routine_view._modality = target_modality
    else:
        routine_view["modality"] = target_modality
    return routine_view


def start_student_workout_session(
    db: Session, user: User, payload: WorkoutSessionStartInput
) -> WorkoutSession:
    relationship, routine_view = _resolve_student_active_routine(db, user)
    routine_id = routine_view.id if isinstance(routine_view, RoutineTemplate) else routine_view["id"]
    valid_day_names = {day_name for _, day_name, _, _, _ in _iter_routine_exercises(routine_view)}
    if payload.day_name not in valid_day_names:
        raise RoutineTemplateError(VALIDATION_ERROR_STATUS, "El día no pertenece a tu rutina activa.")

    session = WorkoutSession(
        student_id=relationship.student_id,
        relationship_id=relationship.id,
        routine_id=routine_id,
        day_name=payload.day_name,
        modality=relationship.routine_modality or "GYM",
        started_at=utc_now(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def finish_student_workout_session(db: Session, user: User, session_id: str) -> WorkoutSession:
    profile = get_student_profile(db, user)
    session = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id,
            WorkoutSession.student_id == profile.id,
        )
    )
    if session is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No encontramos este entrenamiento.")
    if session.finished_at is None:
        session.finished_at = utc_now()
        db.commit()
        db.refresh(session)
    return session


def create_student_workout_log(
    db: Session, user: User, payload: WorkoutSetLogInput
) -> WorkoutSetLog:
    relationship, routine_view = _resolve_student_active_routine(db, user)
    routine_id = routine_view.id if isinstance(routine_view, RoutineTemplate) else routine_view["id"]
    exercises_by_id = {ex.id: ex for _, _, _, _, ex in _iter_routine_exercises(routine_view)}

    exercise = exercises_by_id.get(payload.exercise_id)
    if exercise is None:
        raise RoutineTemplateError(
            VALIDATION_ERROR_STATUS,
            VALIDATION_ERROR_MESSAGE,
            [{"field": "exercise_id", "message": "El ejercicio no pertenece a tu rutina activa."}],
        )

    # US-53: sin variante segura el ejercicio queda bloqueado también del lado del servidor
    from backend.src.services.safe_variant_service import check_for_student

    if check_for_student(db, relationship, exercise)[0] == "BLOCKED":
        detail = (
            f'No se puede registrar "{exercise.name}": no hay una variante segura para tus limitaciones. '
            "Podés saltearlo; tu entrenador ya fue avisado."
        )
        raise RoutineTemplateError(VALIDATION_ERROR_STATUS, detail, [{"field": "exercise_id", "message": detail}])

    workout_session = None
    if payload.session_id:
        workout_session = db.scalar(
            select(WorkoutSession).where(
                WorkoutSession.id == payload.session_id,
                WorkoutSession.student_id == relationship.student_id,
                WorkoutSession.relationship_id == relationship.id,
            )
        )
        if (
            workout_session is None
            or workout_session.finished_at is not None
            or workout_session.routine_id != routine_id
            or workout_session.day_name != payload.day_name
        ):
            raise RoutineTemplateError(VALIDATION_ERROR_STATUS, "La sesión de entrenamiento no está activa o no corresponde a este día.")
        if payload.weight_kg is None:
            raise RoutineTemplateError(
                VALIDATION_ERROR_STATUS,
                "Indicá el peso usado. Para peso corporal, ingresá 0 kg.",
                [{"field": "weight_kg", "message": "Este campo es obligatorio para registrar una serie."}],
            )

    effective_modality = workout_session.modality if workout_session else payload.modality or (relationship.routine_modality or "GYM")
    if effective_modality == "HOME" and not exercise.has_no_materials_alternative:
        detail = (
            f'No se puede registrar en modalidad Casa/Viaje porque "{exercise.name}" '
            'no tiene una alternativa "Sin materiales" cargada.'
        )
        raise RoutineTemplateError(
            VALIDATION_ERROR_STATUS,
            detail,
            [{"field": "modality", "message": detail}],
        )

    log_entry = WorkoutSetLog(
        student_id=relationship.student_id,
        relationship_id=relationship.id,
        routine_id=routine_id,
        day_name=payload.day_name,
        exercise_id=exercise.id,
        exercise_name=exercise.name,
        modality=effective_modality,
        set_number=payload.set_number,
        reps_completed=payload.reps_completed,
        weight_kg=payload.weight_kg,
        duration_seconds=payload.duration_seconds,
        session_id=workout_session.id if workout_session else None,
        recorded_at=utc_now(),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def delete_student_workout_log(db: Session, user: User, log_id: str) -> None:
    relationship, routine_view = _resolve_student_active_routine(db, user)
    routine_id = routine_view.id if isinstance(routine_view, RoutineTemplate) else routine_view["id"]
    log_entry = db.scalar(
        select(WorkoutSetLog).where(
            WorkoutSetLog.id == log_id,
            WorkoutSetLog.student_id == relationship.student_id,
            WorkoutSetLog.relationship_id == relationship.id,
        )
    )
    if log_entry is None:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "No encontramos la serie registrada.")
    if log_entry.session_id is None:
        raise RoutineTemplateError(VALIDATION_ERROR_STATUS, "Solo podés desmarcar series de un entrenamiento en curso.")
    workout_session = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.id == log_entry.session_id,
            WorkoutSession.student_id == relationship.student_id,
            WorkoutSession.relationship_id == relationship.id,
        )
    )
    if (
        workout_session is None
        or workout_session.finished_at is not None
        or workout_session.routine_id != routine_id
    ):
        raise RoutineTemplateError(VALIDATION_ERROR_STATUS, "No se pueden modificar series de un entrenamiento finalizado.")
    db.delete(log_entry)
    db.commit()


def list_student_workout_sessions(db: Session, user: User) -> list[WorkoutSession]:
    profile = get_student_profile(db, user)
    active_rel_ids = select(TrainingRelationship.id).where(
        TrainingRelationship.student_id == profile.id,
        TrainingRelationship.status == "ACTIVE",
    )
    query = select(WorkoutSession).where(
        WorkoutSession.student_id == profile.id,
        WorkoutSession.relationship_id.in_(active_rel_ids),
        WorkoutSession.finished_at.is_not(None),
    ).order_by(WorkoutSession.started_at.desc())
    return list(db.scalars(query))


def list_student_workout_logs(
    db: Session, user: User, exercise_id: str | None = None
) -> list[WorkoutSetLog]:
    profile = get_student_profile(db, user)
    active_rel_ids = select(TrainingRelationship.id).where(
        TrainingRelationship.student_id == profile.id,
        TrainingRelationship.status == "ACTIVE",
    )
    query = select(WorkoutSetLog).where(
        WorkoutSetLog.student_id == profile.id,
        WorkoutSetLog.relationship_id.in_(active_rel_ids),
    )
    if exercise_id is not None:
        query = query.where(WorkoutSetLog.exercise_id == exercise_id)
    query = query.order_by(WorkoutSetLog.recorded_at.desc(), WorkoutSetLog.id.desc())
    return list(db.scalars(query))


def list_trainer_student_workout_logs(
    db: Session, user: User, relationship_id: str
) -> list[WorkoutSetLog]:
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
    query = select(WorkoutSetLog).where(
        WorkoutSetLog.relationship_id == relationship.id,
        WorkoutSetLog.student_id == relationship.student_id,
    ).order_by(WorkoutSetLog.recorded_at.desc(), WorkoutSetLog.id.desc())
    return list(db.scalars(query))


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

    if not rows:
        return []

    rel_ids = [rel.id for rel, _, _ in rows]
    initial_routine_ids = [rel.initial_routine_id for rel, _, _ in rows if rel.initial_routine_id]

    tpl_map: dict[str, str] = {}
    if initial_routine_ids:
        for tpl in db.scalars(
            select(RoutineTemplate).where(
                RoutineTemplate.id.in_(initial_routine_ids),
                RoutineTemplate.trainer_id == trainer.id,
            )
        ):
            tpl_map[tpl.id] = tpl.name

    ar_map: dict[str, str] = {}
    if initial_routine_ids:
        for ar in db.scalars(
            select(AssignedRoutine).where(
                AssignedRoutine.id.in_(initial_routine_ids),
                AssignedRoutine.trainer_id == trainer.id,
                AssignedRoutine.status == "APPROVED",
            )
        ):
            ar_map[ar.id] = ar.name

    sr_map: dict[str, tuple[str, str]] = {}
    if rel_ids:
        for sr in db.scalars(
            select(StudentRoutine).where(
                StudentRoutine.relationship_id.in_(rel_ids),
                StudentRoutine.status != "UNASSIGNED",
            )
        ):
            sr_map[sr.relationship_id] = (sr.id, sr.name)

    assignments: list[dict[str, str | None]] = []
    for relationship, student, student_user in rows:
        routine_template_id = None
        routine_name = None
        if relationship.initial_routine_id:
            if relationship.initial_routine_id in tpl_map:
                routine_template_id = relationship.initial_routine_id
                routine_name = tpl_map[relationship.initial_routine_id]
            elif relationship.initial_routine_id in ar_map:
                routine_template_id = relationship.initial_routine_id
                routine_name = ar_map[relationship.initial_routine_id]
            elif relationship.id in sr_map:
                routine_template_id, routine_name = sr_map[relationship.id]
        else:
            if relationship.id in sr_map:
                routine_template_id, routine_name = sr_map[relationship.id]

        student_name = " ".join(part for part in (student.first_name, student.last_name) if part).strip()
        assignments.append(
            {
                "relationship_id": relationship.id,
                "student_id": student.id,
                "student_name": student_name or student_user.email,
                "routine_template_id": routine_template_id,
                "routine_name": routine_name,
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

    routine: RoutineTemplate | AssignedRoutine | None = None
    if routine_template_id is not None:
        routine = db.scalar(
            select(RoutineTemplate).where(
                RoutineTemplate.id == routine_template_id,
                RoutineTemplate.trainer_id == trainer.id,
            )
        )
        # Una rutina con IA solo se reasigna aprobada y al alumno para el que se adaptó (Principio II).
        if routine is None:
            routine = db.scalar(
                select(AssignedRoutine).where(
                    AssignedRoutine.id == routine_template_id,
                    AssignedRoutine.trainer_id == trainer.id,
                    AssignedRoutine.student_id == relationship.student_id,
                    AssignedRoutine.status == "APPROVED",
                )
            )
        if routine is None:
            raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "Rutina no encontrada.")

    relationship.initial_routine_id = routine_template_id
    if routine is None or (relationship.routine_modality == "HOME" and not _routine_supports_home(routine)):
        relationship.routine_modality = "GYM"
    db.commit()
    return {"relationship_id": relationship.id, "routine_template_id": routine_template_id}
