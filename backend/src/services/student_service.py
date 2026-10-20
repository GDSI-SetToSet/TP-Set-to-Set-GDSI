from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE
from backend.src.models.student_profile import StudentProfile
from backend.src.models.user import User
from backend.src.schemas.student import StudentProfileUpdate


class StudentProfileError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def require_student(user: User) -> None:
    if user.role != STUDENT_ROLE:
        raise StudentProfileError(status.HTTP_403_FORBIDDEN, "This action is available only for students.")


def get_or_create_profile(db: Session, user: User) -> StudentProfile:
    require_student(user)
    if user.student_profile is not None:
        return user.student_profile
    now = utc_now()
    profile = StudentProfile(user_id=user.id, status="DRAFT", created_at=now, updated_at=now)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, user: User, payload: StudentProfileUpdate) -> StudentProfile:
    profile = get_or_create_profile(db, user)
    changes = payload.model_dump(exclude_unset=True)
    
    proposed = {
        "full_name": profile.full_name,
        "birth_date": profile.birth_date,
        "contact_phone": profile.contact_phone,
        **changes,
    }
    
    complete = all(proposed[field] is not None for field in ("full_name", "birth_date", "contact_phone"))
    
    if profile.status == "PUBLISHED" and not complete:
        missing = [field for field in ("full_name", "birth_date", "contact_phone") if proposed[field] is None]
        raise StudentProfileError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A published profile must keep full name, birth date, and contact phone.",
            [{"field": field, "message": "This field is required."} for field in missing],
        )

    for field, value in changes.items():
        setattr(profile, field, value)
        
    profile.status = "PUBLISHED" if complete else "DRAFT"
    profile.updated_at = utc_now()
    db.commit()
    db.refresh(profile)
    return profile