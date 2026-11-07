from copy import deepcopy

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import (
    BODY_AREAS_ES,
    VALIDATION_ERROR_MESSAGE,
    canonical_zone_key,
)
from backend.src.models.assigned_routine import AssignedRoutine
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


def _days_support_home_modality(db: Session, days: list[dict]) -> bool:
    exercise_ids = {entry["exercise_id"] for _, entry in _entries(days)}
    if not exercise_ids:
        return True
    exercises = {
        ex.id: ex
        for ex in db.scalars(select(Exercise).where(Exercise.id.in_(exercise_ids)))
    }
    return all(
        (ex := exercises.get(entry["exercise_id"])) is not None and ex.has_no_materials_alternative
        for _, entry in _entries(days)
    )


def _content_from_assigned_routine(assigned: AssignedRoutine) -> list[dict]:
    return [
        {
            "name": day.name,
            "blocks": [
                {
                    "name": block.name,
                    "estimated_duration_minutes": getattr(block, "estimated_duration_minutes", None),
                    "exercises": [
                        {
                            "exercise_id": e.exercise_id,
                            "sets": e.sets,
                            "reps": e.reps,
                            "rest_seconds": e.rest_seconds,
                            "target_weight_kg": (
                                float(e.target_weight_kg)
                                if getattr(e, "target_weight_kg", None) is not None
                                else None
                            ),
                        }
                        for e in block.exercises
                    ],
                }
                for block in day.blocks
            ],
        }
        for day in assigned.days
    ]


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
    source: RoutineTemplate | AssignedRoutine | None = None
    if relationship.initial_routine_id:
        source = db.get(RoutineTemplate, relationship.initial_routine_id)
        if source is None:
            assigned = db.get(AssignedRoutine, relationship.initial_routine_id)
            if assigned is not None and assigned.status == "APPROVED":
                source = assigned
    if source is None or source.trainer_id != relationship.trainer_id:
        raise RoutineTemplateError(status.HTTP_404_NOT_FOUND, "El alumno no tiene una rutina asignada.")
    now = utc_now()
    is_new = routine is None
    routine = routine or StudentRoutine(relationship_id=relationship.id, created_at=now, draft_version=0)
    _seed(routine, source)
    if is_new:
        routine.draft_version = 0
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


def _seed(routine: StudentRoutine, source: RoutineTemplate | AssignedRoutine) -> None:
    if isinstance(source, AssignedRoutine):
        routine.source_kind = "AI"
        routine.source_template_id = source.template_id or source.id
        routine.name = source.name
        routine.duration_weeks = source.duration_weeks
        routine.intensity = source.intensity
        routine.has_no_materials_alternative = getattr(source, "has_no_materials_alternative", False)
        routine.desired_weekly_volume = None
        routine.days = _content_from_assigned_routine(source)
    else:
        routine.source_kind = "GENERIC"
        routine.source_template_id = source.id
        routine.name = source.name
        routine.duration_weeks = source.duration_weeks
        routine.intensity = source.intensity
        routine.has_no_materials_alternative = source.has_no_materials_alternative
        routine.desired_weekly_volume = None
        routine.days = _content_from_template(source)
    routine.draft = None
    routine.draft_version = (routine.draft_version or 0) + 1
    routine.status = "ACTIVE"
    routine.updated_at = utc_now()


def sync_assigned_routine(
    db: Session, relationship: TrainingRelationship, assigned: AssignedRoutine
) -> StudentRoutine:
    routine = db.scalar(select(StudentRoutine).where(StudentRoutine.relationship_id == relationship.id))
    now = utc_now()
    if routine is None:
        routine = StudentRoutine(
            relationship_id=relationship.id,
            created_at=now,
            draft_version=0,
        )
    _seed(routine, assigned)
    routine.draft_version = 0
    if relationship.routine_modality == "HOME" and not _days_support_home_modality(db, routine.days):
        relationship.routine_modality = "GYM"
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


def _assignable_source(db: Session, routine_id: str | None) -> RoutineTemplate | AssignedRoutine | None:
    if routine_id is None:
        return None
    return db.get(RoutineTemplate, routine_id) or db.get(AssignedRoutine, routine_id)


# El entrenador reasignó la rutina: la copia vigente se reemplaza (el log de cambios se conserva).
def on_reassign(db: Session, relationship_id: str, template_id: str | None) -> None:
    routine = db.scalar(select(StudentRoutine).where(StudentRoutine.relationship_id == relationship_id))
    if routine is None:
        return
    source = _assignable_source(db, template_id)
    if source is None:
        routine.status, routine.draft = "UNASSIGNED", None
    else:
        _seed(routine, source)
    db.commit()


def preserve_student_copies(db: Session, trainer_id: str, routine_id: str) -> None:
    """Deja a cada alumno activo con su copia propia antes de eliminar la rutina de origen."""
    relationships = db.scalars(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer_id,
            TrainingRelationship.initial_routine_id == routine_id,
            TrainingRelationship.status == "ACTIVE",
        )
    ).all()
    for relationship in relationships:
        ensure_routine(db, relationship)
        relationship.initial_routine_id = None


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
    raw_zones = list(
        db.scalars(select(ProtectedZone.body_area).where(ProtectedZone.student_id == relationship.student_id))
    )
    student_canonical: dict[str, str] = {}
    for z in raw_zones:
        if z:
            k = canonical_zone_key(z)
            if k:
                student_canonical[k] = z

    conflicts: list[dict[str, str]] = []
    for field, entry in entries:
        ex = exercises.get(entry["exercise_id"])
        if not ex:
            continue
        ex_canonical = {canonical_zone_key(cz) for cz in (ex.contraindicated_zones or [])}
        matching_keys = sorted(student_canonical.keys() & ex_canonical)
        if matching_keys:
            names = ", ".join(BODY_AREAS_ES.get(k, student_canonical[k]) for k in matching_keys)
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
    """Avisos al asignar una rutina: ejercicios que chocan con las zonas del alumno."""
    source = _assignable_source(db, template_id)
    relationship = db.get(TrainingRelationship, relationship_id)
    if source is None or relationship is None:
        return []
    if isinstance(source, AssignedRoutine):
        content = _content_from_assigned_routine(source)
    else:
        content = _content_from_template(source)
    return [c["message"] for c in find_conflicts(db, relationship, content)[0]]


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


def _diff(routine: StudentRoutine, draft: dict) -> dict:
    fields = ("name", "duration_weeks", "intensity", "has_no_materials_alternative", "desired_weekly_volume")

    # Mapeo por ubicación única (day_idx, block_idx, exercise_id) para evitar colisiones entre días
    before_entries: dict[tuple[int, int, str], dict] = {}
    for di, day in enumerate(routine.days):
        for bi, block in enumerate(day.get("blocks", [])):
            for entry in block.get("exercises", []):
                before_entries[(di, bi, entry["exercise_id"])] = entry

    after_entries: dict[tuple[int, int, str], dict] = {}
    for di, day in enumerate(draft.get("days", [])):
        for bi, block in enumerate(day.get("blocks", [])):
            for entry in block.get("exercises", []):
                after_entries[(di, bi, entry["exercise_id"])] = entry

    before_ids = {e["exercise_id"] for _, e in _entries(routine.days)}
    after_ids = {e["exercise_id"] for _, e in _entries(draft["days"])}

    modified = []
    for key in sorted(before_entries.keys() & after_entries.keys()):
        di, bi, ex_id = key
        if before_entries[key] != after_entries[key]:
            modified.append({
                "exercise_id": ex_id,
                "day_index": di,
                "block_index": bi,
                "before": before_entries[key],
                "after": after_entries[key],
            })

    return {
        "fields": {
            f: {"before": getattr(routine, f), "after": draft.get(f)}
            for f in fields
            if getattr(routine, f) != draft.get(f)
        },
        "added": sorted(after_ids - before_ids),
        "removed": sorted(before_ids - after_ids),
        "modified": modified,
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
    if relationship.routine_modality == "HOME" and not all(
        exercises[e["exercise_id"]].has_no_materials_alternative for _, e in _entries(routine.days)
    ):
        relationship.routine_modality = "GYM"
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
    effective_modality = (relationship.routine_modality or "GYM") if relationship else "GYM"
    if (
        content is None
        and effective_modality == "HOME"
        and not all(exercises[e["exercise_id"]].has_no_materials_alternative for _, e in _entries(src["days"]))
    ):
        effective_modality = "GYM"
        if relationship is not None:
            relationship.routine_modality = "GYM"
            db.commit()
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
        "modality": effective_modality,
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
