from copy import deepcopy

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import BODY_AREAS_ES, VALIDATION_ERROR_MESSAGE
from backend.src.models.exercise import Exercise
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_routine import RoutineChangeLog, StudentRoutine
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.student_routine import RoutineDraftInput
from backend.src.services.routine_template_service import RoutineTemplateError
from backend.src.services.student_service import (
    get_or_create_profile as get_student_profile,
)
from backend.src.services.trainer_service import (
    get_or_create_profile as get_trainer_profile,
)
from backend.src.services.trainer_service import utc_now

UNAVAILABLE_MESSAGE = "El ejercicio no está disponible en tu biblioteca"


def norm(zone: str) -> str:
    return zone.strip().lower()


def _entries(days: list[dict]):
    for di, day in enumerate(days):
        for bi, block in enumerate(day["blocks"]):
            for ei, entry in enumerate(block["exercises"]):
                yield f"days.{di}.blocks.{bi}.exercises.{ei}.exercise_id", entry


def _content_from_template(template: RoutineTemplate) -> list[dict]:
    return [
        {
            "name": day.name,
            "blocks": [
                {
                    "name": block.name,
                    "estimated_duration_minutes": block.estimated_duration_minutes,
                    "exercises": [
                        {
                            "exercise_id": e.exercise_id,
                            "sets": e.sets,
                            "reps": e.reps,
                            "rest_seconds": e.rest_seconds,
                            "target_weight_kg": float(e.target_weight_kg) if e.target_weight_kg is not None else None,
                        }
                        for e in block.exercises
                    ],
                }
                for block in day.blocks
            ],
        }
        for day in template.days
    ]


def active_relationship(db: Session, user: User, student_id: str) -> TrainingRelationship:
    trainer = get_trainer_profile(db, user)
    relationship = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.student_id == student_id,
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if relationship is None:
        raise RoutineTemplateError(status.HTTP_403_FORBIDDEN, "No tenés un vínculo activo con ese alumno.")
    return relationship


# Copia perezosa por alumno: editar nunca toca la plantilla compartida (research D1).
def ensure_routine(db: Session, relationship: TrainingRelationship) -> StudentRoutine:
    routine = db.scalar(select(StudentRoutine).where(StudentRoutine.relationship_id == relationship.id))
    if routine is not None and routine.status != "UNASSIGNED":
        return routine
    template = (
        db.get(RoutineTemplate, relationship.initial_routine_id) if relationship.initial_routine_id else None
    )
    if template is None or template.trainer_id != relationship.trainer_id:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "El alumno no tiene una rutina asignada.")
    now = utc_now()
    is_new = routine is None
    routine = routine or StudentRoutine(relationship_id=relationship.id, created_at=now, draft_version=0)
    _seed(routine, template)
    if is_new:
        routine.draft_version = 0
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


def _seed(routine: StudentRoutine, template: RoutineTemplate) -> None:
    routine.source_template_id = template.id
    routine.name = template.name
    routine.duration_weeks = template.duration_weeks
    routine.intensity = template.intensity
    routine.has_no_materials_alternative = template.has_no_materials_alternative
    routine.desired_weekly_volume = None
    routine.days = _content_from_template(template)
    routine.draft = None
    routine.draft_version = (routine.draft_version or 0) + 1
    routine.status = "ACTIVE"
    routine.updated_at = utc_now()


# El entrenador reasignó la rutina: la copia vigente se reemplaza (el log de cambios se conserva).
def on_reassign(db: Session, relationship_id: str, template_id: str | None) -> None:
    routine = db.scalar(select(StudentRoutine).where(StudentRoutine.relationship_id == relationship_id))
    if routine is None:
        return
    if template_id is None:
        routine.status, routine.draft = "UNASSIGNED", None
    else:
        _seed(routine, db.get(RoutineTemplate, template_id))
    db.commit()


def get_routine(db: Session, user: User, student_id: str) -> StudentRoutine:
    return ensure_routine(db, active_relationship(db, user, student_id))


def find_conflicts(
    db: Session, relationship: TrainingRelationship, days: list[dict]
) -> tuple[list[dict[str, str]], dict[str, Exercise]]:
    """Ejercicios de `days` contraindicados por las zonas protegidas del alumno (bloqueo absoluto)."""
    entries = list(_entries(days))
    exercises = {
        ex.id: ex
        for ex in db.scalars(
            select(Exercise).where(
                Exercise.id.in_({e["exercise_id"] for _, e in entries}), Exercise.trainer_id == relationship.trainer_id
            )
        )
    }
    zones = {
        norm(z)
        for z in db.scalars(select(ProtectedZone.body_area).where(ProtectedZone.student_id == relationship.student_id))
    }
    conflicts: list[dict[str, str]] = []
    for field, entry in entries:
        ex = exercises.get(entry["exercise_id"])
        conflict = sorted(zones & {norm(z) for z in ex.contraindicated_zones}) if ex else []
        if conflict:
            names = ", ".join(BODY_AREAS_ES.get(z, z) for z in conflict)
            conflicts.append({"field": field, "message": f'"{ex.name}" está contraindicado por la limitación del alumno: {names}'})
    return conflicts, exercises


def _validate_draft_content(
    db: Session, relationship: TrainingRelationship, days: list[dict], retained_ids: set[str]
) -> dict[str, Exercise]:
    conflicts, exercises = find_conflicts(db, relationship, days)
    errors = [
        {"field": field, "message": UNAVAILABLE_MESSAGE}
        for field, entry in _entries(days)
        if (ex := exercises.get(entry["exercise_id"])) is None
        or (ex.deleted_at is not None and ex.id not in retained_ids)
    ] + conflicts
    if errors:
        raise RoutineTemplateError(422, VALIDATION_ERROR_MESSAGE, errors)
    return exercises


def current_conflicts(db: Session, routine: StudentRoutine) -> list[dict[str, str]]:
    """Conflictos del contenido que se está mostrando (borrador si existe, si no la versión vigente)."""
    relationship = db.get(TrainingRelationship, routine.relationship_id)
    days = routine.draft["days"] if routine.draft else routine.days
    return find_conflicts(db, relationship, days)[0]


def template_conflicts(db: Session, relationship_id: str, template_id: str | None) -> list[str]:
    """Avisos al asignar una plantilla: ejercicios que chocan con las zonas del alumno."""
    template = db.get(RoutineTemplate, template_id) if template_id else None
    relationship = db.get(TrainingRelationship, relationship_id)
    if template is None or relationship is None:
        return []
    return [c["message"] for c in find_conflicts(db, relationship, _content_from_template(template))[0]]


def save_draft(db: Session, user: User, student_id: str, payload: RoutineDraftInput) -> StudentRoutine:
    routine = ensure_routine(db, active_relationship(db, user, student_id))
    if payload.draft_version != routine.draft_version:
        raise RoutineTemplateError(status.HTTP_409_CONFLICT, "La rutina cambió desde que la abriste. Recargala.")
    data = payload.model_dump(exclude={"draft_version"})
    relationship = db.get(TrainingRelationship, routine.relationship_id)
    retained = {e["exercise_id"] for _, e in _entries(routine.days)}
    _validate_draft_content(db, relationship, data["days"], retained)
    routine.draft = data
    routine.draft_version += 1
    routine.status = "DRAFT_PENDING"
    routine.updated_at = utc_now()
    db.commit()
    db.refresh(routine)
    return routine


def discard_draft(db: Session, user: User, student_id: str) -> None:
    routine = ensure_routine(db, active_relationship(db, user, student_id))
    routine.draft = None
    routine.draft_version += 1
    routine.status = "ACTIVE"
    routine.updated_at = utc_now()
    db.commit()


def _flat(days: list[dict]) -> dict[str, dict]:
    flat: dict[str, dict] = {}
    for _, e in _entries(days):
        flat.setdefault(e["exercise_id"], e)
    return flat


def _diff(routine: StudentRoutine, draft: dict) -> dict:
    before, after = _flat(routine.days), _flat(draft["days"])
    fields = ("name", "duration_weeks", "intensity", "has_no_materials_alternative", "desired_weekly_volume")
    return {
        "fields": {
            f: {"before": getattr(routine, f), "after": draft.get(f)}
            for f in fields
            if getattr(routine, f) != draft.get(f)
        },
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "modified": [
            {"exercise_id": i, "before": before[i], "after": after[i]}
            for i in sorted(before.keys() & after.keys())
            if before[i] != after[i]
        ],
    }


def confirm_draft(db: Session, user: User, student_id: str) -> StudentRoutine:
    relationship = active_relationship(db, user, student_id)
    routine = ensure_routine(db, relationship)
    draft = routine.draft
    if draft is None:
        raise RoutineTemplateError(status.HTTP_409_CONFLICT, "No hay un borrador para confirmar.")
    retained = {e["exercise_id"] for _, e in _entries(routine.days)}
    exercises = _validate_draft_content(db, relationship, draft["days"], retained)
    if draft["has_no_materials_alternative"]:  # solo ejercicios agregados/reemplazados (spec FR-003c)
        errors = [
            {"field": field, "message": f'"{exercises[e["exercise_id"]].name}" no tiene alternativa "Sin materiales"'}
            for field, e in _entries(draft["days"])
            if e["exercise_id"] not in retained and not exercises[e["exercise_id"]].has_no_materials_alternative
        ]
        if errors:
            raise RoutineTemplateError(422, VALIDATION_ERROR_MESSAGE, errors)
    now = utc_now()
    db.add(
        RoutineChangeLog(
            student_routine_id=routine.id,
            trainer_id=relationship.trainer_id,
            confirmed_at=now,
            changes=_diff(routine, draft),
        )
    )
    for field in ("name", "duration_weeks", "intensity", "has_no_materials_alternative", "desired_weekly_volume"):
        setattr(routine, field, draft[field])
    routine.days = deepcopy(draft["days"])
    routine.draft = None
    routine.draft_version += 1
    routine.status = "ACTIVE"
    routine.updated_at = now
    db.commit()
    db.refresh(routine)
    return routine


def render(db: Session, routine: StudentRoutine, content: dict | None = None) -> dict:
    """Arma la forma de RoutineTemplateResponse; content=None renderiza lo vigente."""
    src = content or {
        "name": routine.name,
        "duration_weeks": routine.duration_weeks,
        "intensity": routine.intensity,
        "has_no_materials_alternative": routine.has_no_materials_alternative,
        "days": routine.days,
    }
    relationship = db.get(TrainingRelationship, routine.relationship_id)
    trainer = relationship.trainer
    exercises = {
        ex.id: ex
        for ex in db.scalars(select(Exercise).where(Exercise.id.in_({e["exercise_id"] for _, e in _entries(src["days"])})))
    }
    days = [
        {
            "id": f"{routine.id}-d{di}",
            "name": day["name"],
            "blocks": [
                {
                    "id": f"{routine.id}-d{di}b{bi}",
                    "name": block["name"],
                    "estimated_duration_minutes": block.get("estimated_duration_minutes"),
                    "exercises": [
                        {
                            "id": f"{routine.id}-d{di}b{bi}e{ei}",
                            "sets": e["sets"],
                            "reps": e["reps"],
                            "rest_seconds": e["rest_seconds"],
                            "target_weight_kg": e.get("target_weight_kg"),
                            "exercise": exercises[e["exercise_id"]],
                        }
                        for ei, e in enumerate(block["exercises"])
                    ],
                }
                for bi, block in enumerate(day["blocks"])
            ],
        }
        for di, day in enumerate(src["days"])
    ]
    return {
        "id": routine.id,
        "trainer_id": relationship.trainer_id,
        "trainer_name": trainer.full_name,
        "name": src["name"],
        "duration_weeks": src["duration_weeks"],
        "intensity": src["intensity"],
        "has_no_materials_alternative": src["has_no_materials_alternative"],
        "exercise_count": sum(len(b["exercises"]) for d in days for b in d["blocks"]),
        "days": days,
    }


def student_assigned_view(db: Session, user: User) -> dict | None:
    """Versión vigente de la copia del alumno (nunca el borrador); None si aún no hay copia."""
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
    return render(db, routine) if routine else None
