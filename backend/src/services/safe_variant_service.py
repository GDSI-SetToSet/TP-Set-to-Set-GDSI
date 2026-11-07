from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.exercise import Exercise
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.safe_variant import ExerciseSafeVariant, SafeVariantCase
from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.safe_variant import SafeVariantInput, SafeVariantZones
from backend.src.services.exercise_service import ExerciseError, get_own_exercise
from backend.src.services.notification_service import create_notification
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.trainer_service import utc_now

NO_VARIANT_MESSAGE = "No hay una variante segura para este ejercicio. Podés saltearlo; avisamos a tu entrenador."


def _norm(zones) -> set[str]:
    return {z.strip().lower() for z in zones}


def student_zones(db: Session, student_id: str) -> set[str]:
    return _norm(db.scalars(select(ProtectedZone.body_area).where(ProtectedZone.student_id == student_id)))


def resolve_variant(db: Session, exercise: Exercise, zones: set[str]) -> tuple[str, Exercise | None]:
    """Resolución pura (sin escrituras): SAFE | VARIANT | BLOCKED según las zonas del alumno (research D11)."""
    conflict = zones & _norm(exercise.contraindicated_zones)
    if not conflict:
        return "SAFE", None
    rows = db.execute(
        select(ExerciseSafeVariant, Exercise)
        .join(Exercise, Exercise.id == ExerciseSafeVariant.variant_exercise_id)
        .where(ExerciseSafeVariant.exercise_id == exercise.id, Exercise.deleted_at.is_(None))
        .order_by(ExerciseSafeVariant.created_at, ExerciseSafeVariant.id)
    )
    for link, variant in rows:
        # cubre todo el conflicto y la variante en sí no daña ninguna otra zona del alumno
        if conflict <= _norm(link.covered_zones) and not zones & _norm(variant.contraindicated_zones):
            return "VARIANT", variant
    return "BLOCKED", None


def _zone_error(field: str, message: str) -> ExerciseError:
    return ExerciseError(422, "Datos inválidos", [{"field": field, "message": message}])


def _validate(exercise: Exercise, variant: Exercise, zones: list[str]) -> None:
    if not set(zones) <= _norm(exercise.contraindicated_zones):
        raise _zone_error("covered_zones", "Las zonas deben ser contraindicaciones del ejercicio de riesgo.")
    if set(zones) & _norm(variant.contraindicated_zones):
        raise _zone_error("variant_exercise_id", "La variante está contraindicada para esas zonas.")


def _own_link(db: Session, exercise: Exercise, variant_id: str) -> ExerciseSafeVariant:
    link = db.scalar(
        select(ExerciseSafeVariant).where(
            ExerciseSafeVariant.exercise_id == exercise.id, ExerciseSafeVariant.id == variant_id
        )
    )
    if link is None:
        raise ExerciseError(status.HTTP_404_NOT_FOUND, "Variante no encontrada.")
    return link


def list_variants(db: Session, user: User, exercise_id: str) -> list[dict]:
    exercise = get_own_exercise(db, user, exercise_id)
    rows = db.execute(
        select(ExerciseSafeVariant, Exercise.name)
        .join(Exercise, Exercise.id == ExerciseSafeVariant.variant_exercise_id)
        .where(ExerciseSafeVariant.exercise_id == exercise.id)
        .order_by(ExerciseSafeVariant.created_at)
    )
    return [
        {"id": l.id, "variant_exercise_id": l.variant_exercise_id, "variant_name": name, "covered_zones": l.covered_zones}
        for l, name in rows
    ]


def create_variant(db: Session, user: User, exercise_id: str, payload: SafeVariantInput) -> ExerciseSafeVariant:
    exercise = get_own_exercise(db, user, exercise_id)
    try:
        variant = get_own_exercise(db, user, payload.variant_exercise_id)
    except ExerciseError:
        raise _zone_error("variant_exercise_id", "El ejercicio variante no está disponible en tu biblioteca.") from None
    if variant.id == exercise.id:
        raise _zone_error("variant_exercise_id", "Un ejercicio no puede ser variante de sí mismo.")
    _validate(exercise, variant, payload.covered_zones)
    if db.scalar(
        select(ExerciseSafeVariant.id).where(
            ExerciseSafeVariant.exercise_id == exercise.id, ExerciseSafeVariant.variant_exercise_id == variant.id
        )
    ):
        raise ExerciseError(status.HTTP_409_CONFLICT, "Esa variante ya está vinculada.")
    now = utc_now()
    link = ExerciseSafeVariant(
        exercise_id=exercise.id,
        variant_exercise_id=variant.id,
        covered_zones=payload.covered_zones,
        created_at=now,
        updated_at=now,
    )
    db.add(link)
    db.flush()
    _close_covered_cases(db, exercise)
    db.commit()
    db.refresh(link)
    return link


def update_variant(
    db: Session, user: User, exercise_id: str, variant_id: str, payload: SafeVariantZones
) -> ExerciseSafeVariant:
    exercise = get_own_exercise(db, user, exercise_id)
    link = _own_link(db, exercise, variant_id)
    _validate(exercise, db.get(Exercise, link.variant_exercise_id), payload.covered_zones)
    link.covered_zones = payload.covered_zones
    link.updated_at = utc_now()
    db.flush()
    _close_covered_cases(db, exercise)
    db.commit()
    db.refresh(link)
    return link


def delete_variant(db: Session, user: User, exercise_id: str, variant_id: str) -> None:
    link = _own_link(db, get_own_exercise(db, user, exercise_id), variant_id)
    db.delete(link)
    db.commit()


def _close_covered_cases(db: Session, exercise: Exercise) -> None:
    for case in db.scalars(
        select(SafeVariantCase).where(SafeVariantCase.exercise_id == exercise.id, SafeVariantCase.status == "PENDING")
    ):
        if resolve_variant(db, exercise, student_zones(db, case.student_id))[0] != "BLOCKED":
            case.status, case.resolved_at = "RESOLVED", utc_now()


def _track_case(db: Session, relationship: TrainingRelationship, exercise: Exercise, blocked: bool) -> None:
    now = utc_now()
    case = db.scalar(
        select(SafeVariantCase).where(
            SafeVariantCase.student_id == relationship.student_id, SafeVariantCase.exercise_id == exercise.id
        )
    )
    if not blocked:
        if case is not None and case.status == "PENDING":
            case.status, case.resolved_at = "RESOLVED", now
        return
    if case is not None and case.status == "PENDING":
        return  # ya se avisó al entrenador: una sola notificación por caso pendiente
    if case is None:
        case = SafeVariantCase(student_id=relationship.student_id, exercise_id=exercise.id, created_at=now)
        db.add(case)
    case.status, case.resolved_at = "PENDING", None
    db.flush()
    student = db.get(StudentProfile, relationship.student_id)
    name = f"{student.first_name or ''} {student.last_name or ''}".strip() or "Un alumno"
    create_notification(
        db,
        recipient_id=relationship.trainer.user_id,  # users.id, no el id del perfil
        type="SAFE_VARIANT_MISSING",
        title="Falta una variante segura",
        message=f'{name} consultó "{exercise.name}" y no hay una variante segura que cubra sus restricciones.',
        related_entity_type="SAFE_VARIANT_CASE",
        related_entity_id=case.id,
    )


def resolve_for_student(db: Session, user: User, exercise_id: str) -> dict:
    from backend.src.services.student_routine_service import (
        current_exercise_ids,  # evita import circular
    )

    profile = get_student_profile(db, user)
    relationship = db.scalar(
        select(TrainingRelationship)
        .where(TrainingRelationship.student_id == profile.id, TrainingRelationship.status == "ACTIVE")
        .order_by(TrainingRelationship.start_date.desc())
    )
    if relationship is None:
        raise ExerciseError(status.HTTP_403_FORBIDDEN, "No tenés un vínculo activo con un entrenador.")
    exercise = db.get(Exercise, exercise_id)
    if exercise is None or exercise_id not in current_exercise_ids(db, relationship):
        raise ExerciseError(status.HTTP_404_NOT_FOUND, "Ejercicio no encontrado en tu rutina.")
    result, variant = resolve_variant(db, exercise, student_zones(db, profile.id))
    _track_case(db, relationship, exercise, blocked=result == "BLOCKED")
    db.commit()
    if result == "VARIANT":
        return {
            "status": result,
            "variant": {
                "exercise_id": variant.id,
                "name": variant.name,
                "description": variant.description,
                "video_url": variant.video_url,
                "video_platform": variant.video_platform.value
                if hasattr(variant.video_platform, "value")
                else variant.video_platform,
            },
        }
    if result == "BLOCKED":
        return {"status": result, "message": NO_VARIANT_MESSAGE, "can_skip": True}
    return {"status": result}
