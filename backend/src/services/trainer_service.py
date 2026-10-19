from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.orm import Session

from backend.src.core.constants import TRAINER_ROLE
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.user import User
from backend.src.schemas.trainer import TrainerProfileUpdate


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
