from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.constants import TRAINER_ROLE
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.user import User
from backend.src.schemas.trainer import (
    TrainerProfileUpdate,
    TrainerQuotaUpdate,
    TrainingPlanCreate,
    TrainingPlanUpdate,
)


class TrainerProfileError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def require_trainer(user: User) -> None:
    if user.role != TRAINER_ROLE:
        raise TrainerProfileError(status.HTTP_403_FORBIDDEN, "Esta acción está disponible solo para entrenadores.")


def get_or_create_profile(db: Session, user: User) -> TrainerProfile:
    require_trainer(user)
    if user.trainer_profile is not None:
        return user.trainer_profile
    now = utc_now()
    profile = TrainerProfile(user_id=user.id, status="DRAFT", max_students=0, created_at=now, updated_at=now)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, user: User, payload: TrainerProfileUpdate) -> TrainerProfile:
    profile = get_or_create_profile(db, user)
    changes = payload.model_dump(exclude_unset=True)
    proposed = {
        "full_name": profile.full_name,
        "contact_phone": profile.contact_phone,
        "specialty": profile.specialty,
        **changes,
    }
    complete = all(proposed[field] for field in ("full_name", "contact_phone", "specialty"))
    if profile.status == "PUBLISHED" and not complete:
        missing = [field for field in ("full_name", "contact_phone", "specialty") if not proposed[field]]
        raise TrainerProfileError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Un perfil publicado debe conservar nombre, contacto y especialidad.",
            [{"field": field, "message": "Este campo es obligatorio."} for field in missing],
        )
    for field, value in changes.items():
        setattr(profile, field, value)
    profile.status = "PUBLISHED" if complete else "DRAFT"
    profile.updated_at = utc_now()
    db.commit()
    db.refresh(profile)
    return profile


def get_published_profile(db: Session, profile_id: str) -> TrainerProfile:
    profile = db.get(TrainerProfile, profile_id)
    if profile is None or profile.status != "PUBLISHED":
        raise TrainerProfileError(status.HTTP_404_NOT_FOUND, "Perfil de entrenador no encontrado.")
    return profile


# Los vínculos entrenador-alumno llegan con las specs 004/011: hasta entonces no hay alumnos activos.
# Al integrarlos, este conteo y el bloqueo transaccional de aceptación completan la T026.
def count_active_students(db: Session, profile: TrainerProfile) -> int:
    return 0


def quota_summary(db: Session, profile: TrainerProfile) -> dict[str, int | bool]:
    active = count_active_students(db, profile)
    available = max(profile.max_students - active, 0)
    return {
        "max_students": profile.max_students,
        "active_students": active,
        "available_slots": available,
        "has_available_quota": available > 0,
    }


def has_available_quota(db: Session, profile: TrainerProfile) -> bool:
    return bool(quota_summary(db, profile)["has_available_quota"])


def update_quota(db: Session, user: User, payload: TrainerQuotaUpdate) -> TrainerProfile:
    profile = get_or_create_profile(db, user)
    profile.max_students = payload.max_students
    profile.updated_at = utc_now()
    db.commit()
    db.refresh(profile)
    return profile


def list_own_plans(db: Session, user: User) -> list[TrainingPlan]:
    profile = get_or_create_profile(db, user)
    return list(profile.plans)


def create_plan(db: Session, user: User, payload: TrainingPlanCreate) -> TrainingPlan:
    profile = get_or_create_profile(db, user)
    now = utc_now()
    plan = TrainingPlan(trainer_id=profile.id, **payload.model_dump(), is_active=True, created_at=now, updated_at=now)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_own_plan(db: Session, user: User, plan_id: str) -> TrainingPlan:
    profile = get_or_create_profile(db, user)
    plan = db.get(TrainingPlan, plan_id)
    if plan is None or plan.trainer_id != profile.id:
        raise TrainerProfileError(status.HTTP_404_NOT_FOUND, "Paquete no encontrado.")
    return plan


# No retroactividad (US-03): editar o archivar solo cambia la oferta para solicitudes futuras.
# Los vínculos activos deben guardar su propio arancel al aceptarse, sin referenciar el precio vigente del paquete.
def update_plan(db: Session, user: User, plan_id: str, payload: TrainingPlanUpdate) -> TrainingPlan:
    plan = get_own_plan(db, user, plan_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    plan.updated_at = utc_now()
    db.commit()
    db.refresh(plan)
    return plan


def archive_plan(db: Session, user: User, plan_id: str) -> TrainingPlan:
    plan = get_own_plan(db, user, plan_id)
    plan.is_active = False
    plan.updated_at = utc_now()
    db.commit()
    db.refresh(plan)
    return plan


def list_published_plans(db: Session, profile_id: str) -> list[TrainingPlan]:
    profile = get_published_profile(db, profile_id)
    query = (
        select(TrainingPlan)
        .where(TrainingPlan.trainer_id == profile.id, TrainingPlan.is_active.is_(True))
        .order_by(TrainingPlan.created_at)
    )
    return list(db.scalars(query))
