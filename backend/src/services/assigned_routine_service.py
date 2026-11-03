import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.src.models.assigned_routine import (
    AssignedRoutine,
    AssignedRoutineBlock,
    AssignedRoutineDay,
    AssignedRoutineExercise,
)
from backend.src.models.exercise import Exercise
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.assigned_routine import (
    ActiveStudentResponse,
    GenerateAIRoutineInput,
    TrainerAIRoutineResponse,
)
from backend.src.services.ai_routine_adapter import (
    INTENSITY_ORDER,
    REST_MAX_SECONDS,
    REST_MIN_SECONDS,
    SETS_MAX,
    SETS_MIN,
    AIRoutineAdapterError,
    AIRoutineProposalResult,
    _conflicts_with_zones,
    get_ai_routine_adapter,
    is_valid_reps_format,
)
from backend.src.services.student_service import (
    current_questionnaire,
)
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.trainer_service import (
    get_or_create_profile as get_trainer_profile,
)
from backend.src.services.trainer_service import (
    require_trainer,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


def calculate_age(birth_date: datetime | date | None) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    b_date = birth_date.date() if isinstance(birth_date, datetime) else birth_date
    age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
    return age if age >= 0 else None


class AssignedRoutineError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, Any]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def validate_ai_proposal_domain_rules(
    proposal_result: AIRoutineProposalResult,
    template: RoutineTemplate,
    trainer_exercises: list[Exercise],
    protected_zones: list[ProtectedZone],
) -> None:
    """Valida en el backend que la propuesta de IA respete el catálogo y rangos del dominio."""
    if proposal_result.intensity not in INTENSITY_ORDER:
        raise AssignedRoutineError(
            status.HTTP_502_BAD_GATEWAY,
            f"La propuesta de IA contiene una intensidad inválida ('{proposal_result.intensity}').",
        )

    if not (1 <= proposal_result.duration_weeks <= 52):
        raise AssignedRoutineError(
            status.HTTP_502_BAD_GATEWAY,
            "La propuesta de IA contiene una duración en semanas fuera del rango permitido (1 a 52).",
        )

    allowed_exercises: dict[str, Exercise] = {
        ex.id: ex for ex in trainer_exercises if ex.deleted_at is None
    }
    for day in template.days:
        for block in day.blocks:
            for entry in block.exercises:
                if entry.exercise.deleted_at is None:
                    allowed_exercises.setdefault(entry.exercise_id, entry.exercise)

    for day_data in proposal_result.days:
        for block_data in day_data.blocks:
            for ex_data in block_data.exercises:
                exercise = allowed_exercises.get(ex_data.exercise_id)
                if not exercise:
                    raise AssignedRoutineError(
                        status.HTTP_502_BAD_GATEWAY,
                        f"La propuesta de IA referencia un ejercicio inexistente o no permitido ('{ex_data.exercise_id}').",
                    )
                conflict = _conflicts_with_zones(exercise, protected_zones)
                if conflict:
                    raise AssignedRoutineError(
                        status.HTTP_502_BAD_GATEWAY,
                        f"La propuesta de IA incluye el ejercicio '{exercise.name}' que compromete la zona protegida '{conflict}'.",
                    )
                if not (SETS_MIN <= ex_data.sets <= SETS_MAX):
                    raise AssignedRoutineError(
                        status.HTTP_502_BAD_GATEWAY,
                        f"La propuesta de IA contiene series fuera del rango válido ({SETS_MIN}-{SETS_MAX}).",
                    )
                reps_clean = (ex_data.reps or "").strip()
                if not is_valid_reps_format(reps_clean):
                    raise AssignedRoutineError(
                        status.HTTP_502_BAD_GATEWAY,
                        f"La propuesta de IA contiene repeticiones vacías o con un formato inválido ('{reps_clean}').",
                    )
                if not (REST_MIN_SECONDS <= ex_data.rest_seconds <= REST_MAX_SECONDS):
                    raise AssignedRoutineError(
                        status.HTTP_502_BAD_GATEWAY,
                        f"La propuesta de IA contiene un descanso fuera del rango válido ({REST_MIN_SECONDS}-{REST_MAX_SECONDS}s).",
                    )


def list_active_students_for_trainer(db: Session, user: User) -> list[ActiveStudentResponse]:
    require_trainer(user)
    trainer_profile = get_trainer_profile(db, user)

    relationships = list(
        db.scalars(
            select(TrainingRelationship).where(
                TrainingRelationship.trainer_id == trainer_profile.id,
                TrainingRelationship.status == "ACTIVE",
            )
        )
    )

    if not relationships:
        return []

    student_ids = [rel.student_id for rel in relationships]
    students = list(
        db.scalars(
            select(StudentProfile)
            .where(StudentProfile.id.in_(student_ids))
            .options(selectinload(StudentProfile.protected_zones))
        )
    )
    student_map = {s.id: s for s in students}

    results: list[ActiveStudentResponse] = []
    for rel in relationships:
        student = student_map.get(rel.student_id)
        if not student:
            continue
        full_name = f"{student.first_name or ''} {student.last_name or ''}".strip() or "Alumno/a"
        age = calculate_age(student.birth_date)
        results.append(
            ActiveStudentResponse(
                relationship_id=rel.id,
                student_id=student.id,
                full_name=full_name,
                age=age,
                fitness_goals=student.fitness_goals or [],
                protected_zones_count=len(student.protected_zones),
            )
        )
    return results


def generate_ai_routine_proposal(
    db: Session, user: User, payload: GenerateAIRoutineInput
) -> AssignedRoutine:
    require_trainer(user)
    trainer_profile = get_trainer_profile(db, user)

    # 1. Validar existencia del alumno
    student = db.get(StudentProfile, payload.student_id)
    if not student:
        raise AssignedRoutineError(status.HTTP_404_NOT_FOUND, "Alumno no encontrado.")

    # 2. Validar que exista un vínculo activo entre el entrenador y el alumno (Principio III)
    has_active_rel = db.scalar(
        select(TrainingRelationship.id).where(
            TrainingRelationship.trainer_id == trainer_profile.id,
            TrainingRelationship.student_id == student.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if not has_active_rel:
        raise AssignedRoutineError(
            status.HTTP_403_FORBIDDEN,
            "No tenés un vínculo activo con este alumno para generarle una rutina.",
        )

    # 3. Validar existencia y propiedad de la rutina genérica base
    template = db.get(RoutineTemplate, payload.template_id)
    if not template or template.trainer_id != trainer_profile.id:
        raise AssignedRoutineError(status.HTTP_404_NOT_FOUND, "Rutina genérica no encontrada.")

    # 4. Obtener datos de salud y catálogo de ejercicios del entrenador
    questionnaire = current_questionnaire(db, student)
    protected_zones = list(student.protected_zones)
    trainer_exercises = list(
        db.scalars(
            select(Exercise).where(
                Exercise.trainer_id == trainer_profile.id,
                Exercise.deleted_at.is_(None),
            )
        )
    )

    # 5. Ejecutar adaptación con el motor de IA (sin fallback silencioso)
    try:
        adapter = get_ai_routine_adapter(provider_override=payload.provider)
        proposal_result = adapter.generate_adapted_routine(
            template=template,
            student=student,
            questionnaire=questionnaire,
            protected_zones=protected_zones,
            trainer_exercises=trainer_exercises,
        )
    except AIRoutineAdapterError as exc:
        raise AssignedRoutineError(exc.status_code, exc.detail) from exc
    except Exception as exc:
        logger.error(
            "Falla inesperada en el mecanismo de adaptación con IA (%s).",
            type(exc).__name__,
        )
        raise AssignedRoutineError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Falla interna en el mecanismo de adaptación con IA. Intentá nuevamente más tarde.",
        ) from exc

    # 6. Validar reglas de seguridad y dominio sobre la propuesta generada
    validate_ai_proposal_domain_rules(
        proposal_result=proposal_result,
        template=template,
        trainer_exercises=trainer_exercises,
        protected_zones=protected_zones,
    )

    # 7. Persistir la propuesta en estado 'PENDING_REVIEW' (Human-in-the-Loop)
    now = utc_now()
    assigned_routine = AssignedRoutine(
        trainer_id=trainer_profile.id,
        student_id=student.id,
        template_id=template.id,
        name=proposal_result.name,
        duration_weeks=proposal_result.duration_weeks,
        intensity=proposal_result.intensity,
        has_no_materials_alternative=getattr(
            proposal_result, "has_no_materials_alternative", template.has_no_materials_alternative
        ),
        status="PENDING_REVIEW",
        adaptation_summary=proposal_result.adaptation_summary,
        created_at=now,
        updated_at=now,
    )

    # Construir días, bloques y ejercicios de la propuesta
    assigned_routine.days = [
        AssignedRoutineDay(
            order_index=day_data.order_index,
            name=day_data.name,
            blocks=[
                AssignedRoutineBlock(
                    order_index=block_data.order_index,
                    name=block_data.name,
                    estimated_duration_minutes=block_data.estimated_duration_minutes,
                    exercises=[
                        AssignedRoutineExercise(
                            order_index=ex_data.order_index,
                            exercise_id=ex_data.exercise_id,
                            sets=ex_data.sets,
                            reps=ex_data.reps,
                            rest_seconds=ex_data.rest_seconds,
                            adaptation_notes=ex_data.adaptation_notes,
                            target_weight_kg=Decimal(str(ex_data.target_weight_kg))
                            if ex_data.target_weight_kg is not None
                            else None,
                        )
                        for ex_data in block_data.exercises
                    ],
                )
                for block_data in day_data.blocks
            ],
        )
        for day_data in proposal_result.days
    ]

    db.add(assigned_routine)
    db.commit()
    db.refresh(assigned_routine)
    return assigned_routine


def approve_assigned_routine(db: Session, user: User, routine_id: str) -> AssignedRoutine:
    require_trainer(user)
    trainer_profile = get_trainer_profile(db, user)

    routine = db.get(AssignedRoutine, routine_id)
    if not routine:
        raise AssignedRoutineError(status.HTTP_404_NOT_FOUND, "Rutina no encontrada.")

    if routine.trainer_id != trainer_profile.id:
        raise AssignedRoutineError(status.HTTP_403_FORBIDDEN, "No sos el entrenador autor de esta rutina.")

    relationship = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer_profile.id,
            TrainingRelationship.student_id == routine.student_id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if not relationship:
        raise AssignedRoutineError(
            status.HTTP_403_FORBIDDEN,
            "No tenés un vínculo activo con este alumno para aprobar la rutina.",
        )

    if routine.status == "APPROVED":
        raise AssignedRoutineError(status.HTTP_409_CONFLICT, "La rutina ya fue aprobada previamente.")

    now = utc_now()
    routine.status = "APPROVED"
    routine.approved_at = now
    routine.updated_at = now

    relationship.initial_routine_id = routine.id

    from backend.src.services.student_routine_service import sync_assigned_routine

    sync_assigned_routine(db, relationship, routine)

    db.commit()
    db.refresh(routine)
    return routine


def list_trainer_ai_routines(db: Session, user: User) -> list[TrainerAIRoutineResponse]:
    """Rutinas con IA del entrenador; el vínculo activo se exige porque el resumen expone datos de salud."""
    require_trainer(user)
    trainer_profile = get_trainer_profile(db, user)
    rows = db.execute(
        select(AssignedRoutine, TrainingRelationship)
        .join(
            TrainingRelationship,
            (TrainingRelationship.student_id == AssignedRoutine.student_id)
            & (TrainingRelationship.trainer_id == AssignedRoutine.trainer_id),
        )
        .where(
            AssignedRoutine.trainer_id == trainer_profile.id,
            TrainingRelationship.status == "ACTIVE",
        )
        .order_by(AssignedRoutine.created_at.desc())
    ).all()
    return [
        TrainerAIRoutineResponse.model_validate(routine).model_copy(
            update={
                "student_name": f"{routine.student.first_name or ''} {routine.student.last_name or ''}".strip()
                or "Alumno/a",
                "relationship_id": relationship.id,
                "is_assigned": relationship.initial_routine_id == routine.id,
            }
        )
        for routine, relationship in rows
    ]


def delete_assigned_routine(db: Session, user: User, routine_id: str) -> None:
    from backend.src.services.student_routine_service import preserve_student_copies

    require_trainer(user)
    trainer_profile = get_trainer_profile(db, user)
    routine = db.get(AssignedRoutine, routine_id)
    if routine is None or routine.trainer_id != trainer_profile.id:
        raise AssignedRoutineError(status.HTTP_404_NOT_FOUND, "Rutina no encontrada.")
    preserve_student_copies(db, trainer_profile.id, routine.id)
    db.delete(routine)
    db.commit()


def get_assigned_routine_detail(db: Session, user: User, routine_id: str) -> AssignedRoutine:
    routine = db.get(AssignedRoutine, routine_id)
    if not routine:
        raise AssignedRoutineError(status.HTTP_404_NOT_FOUND, "Rutina no encontrada.")

    if user.role == "TRAINER":
        trainer_profile = get_trainer_profile(db, user)
        if routine.trainer_id != trainer_profile.id:
            raise AssignedRoutineError(status.HTTP_403_FORBIDDEN, "No tenés permiso para ver esta rutina.")
        has_active_rel = db.scalar(
            select(TrainingRelationship.id).where(
                TrainingRelationship.trainer_id == trainer_profile.id,
                TrainingRelationship.student_id == routine.student_id,
                TrainingRelationship.status == "ACTIVE",
            )
        )
        if not has_active_rel:
            raise AssignedRoutineError(
                status.HTTP_403_FORBIDDEN, "No tenés un vínculo activo con este alumno."
            )
    elif user.role == "STUDENT":
        student_profile = get_student_profile(db, user)
        if routine.student_id != student_profile.id:
            raise AssignedRoutineError(status.HTTP_403_FORBIDDEN, "No tenés permiso para ver esta rutina.")
        has_active_rel = db.scalar(
            select(TrainingRelationship.id).where(
                TrainingRelationship.trainer_id == routine.trainer_id,
                TrainingRelationship.student_id == student_profile.id,
                TrainingRelationship.status == "ACTIVE",
            )
        )
        if not has_active_rel:
            raise AssignedRoutineError(
                status.HTTP_403_FORBIDDEN, "No tenés un vínculo activo con este entrenador."
            )
        # El alumno solo puede consultar rutinas aprobadas por su entrenador
        if routine.status != "APPROVED":
            raise AssignedRoutineError(
                status.HTTP_403_FORBIDDEN,
                "La rutina aún está en revisión por tu entrenador.",
            )
    else:
        raise AssignedRoutineError(status.HTTP_403_FORBIDDEN, "Rol no autorizado.")

    return routine


def get_active_routine_for_student(db: Session, user: User) -> AssignedRoutine | None:
    student_profile = get_student_profile(db, user)
    # Busca la rutina aprobada más reciente del alumno con vínculo activo
    query = (
        select(AssignedRoutine)
        .join(
            TrainingRelationship,
            (TrainingRelationship.student_id == AssignedRoutine.student_id)
            & (TrainingRelationship.trainer_id == AssignedRoutine.trainer_id),
        )
        .where(
            AssignedRoutine.student_id == student_profile.id,
            AssignedRoutine.status == "APPROVED",
            TrainingRelationship.status == "ACTIVE",
        )
        .order_by(AssignedRoutine.approved_at.desc(), AssignedRoutine.created_at.desc())
    )
    return db.scalars(query).first()
