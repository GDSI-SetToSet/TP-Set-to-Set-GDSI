from datetime import UTC, date, datetime
from pathlib import Path

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.core.storage import StorageError, open_upload, save_upload
from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.medical_clearance import MedicalClearance
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.training_request import TrainingRequest
from backend.src.models.user import User
from backend.src.schemas.protected_zone import ProtectedZonesUpdate
from backend.src.schemas.student import StudentProfileUpdate
from backend.src.schemas.student_health import HealthQuestionnaireInput
from fastapi import UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session


class StudentProfileError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


REQUIRED_FIELDS = ("first_name", "last_name", "birth_date", "contact_phone", "fitness_goals")


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
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "birth_date": profile.birth_date,
        "contact_phone": profile.contact_phone,
        "fitness_goals": profile.fitness_goals,
        **changes,
    }

    # Onboarding complete = personal data + at least one goal; motivation is optional.
    missing = [field for field in REQUIRED_FIELDS if not proposed[field]]
    complete = not missing

    if profile.status == "PUBLISHED" and not complete:
        raise StudentProfileError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A published profile must keep first name, last name, birth date, contact phone, and at least one goal.",
            [{"field": field, "message": "This field is required."} for field in missing],
        )

    for field, value in changes.items():
        setattr(profile, field, value)

    profile.status = "PUBLISHED" if complete else "DRAFT"
    profile.updated_at = utc_now()
    db.commit()
    db.refresh(profile)
    return profile


def get_own_protected_zones(db: Session, user: User) -> list[ProtectedZone]:
    profile = get_or_create_profile(db, user)
    return list(profile.protected_zones)


def replace_own_protected_zones(
    db: Session, user: User, payload: ProtectedZonesUpdate
) -> list[ProtectedZone]:
    profile = get_or_create_profile(db, user)
    now = utc_now()
    profile.protected_zones.clear()
    db.flush()
    profile.protected_zones = [
        ProtectedZone(body_area=body_area, created_at=now) for body_area in payload.zones
    ]
    profile.updated_at = now
    db.commit()
    db.refresh(profile)
    return list(profile.protected_zones)


def trainer_has_access(db: Session, trainer: User, student_profile_id: str) -> bool:
    if trainer.role != TRAINER_ROLE or not student_profile_id:
        return False
    trainer_profile_id = db.scalar(
        select(TrainerProfile.id).where(TrainerProfile.user_id == trainer.id)
    )
    if trainer_profile_id is None:
        return False
    student_exists = db.scalar(
        select(StudentProfile.id).where(StudentProfile.id == student_profile_id)
    )
    if student_exists is None:
        return False
    pending_request = db.scalar(
        select(TrainingRequest.id).where(
            TrainingRequest.trainer_id == trainer_profile_id,
            TrainingRequest.student_id == student_profile_id,
            TrainingRequest.status == "PENDING",
        )
    )
    if pending_request is not None:
        return True
    active_relationship = db.scalar(
        select(TrainingRelationship.id).where(
            TrainingRelationship.trainer_id == trainer_profile_id,
            TrainingRelationship.student_id == student_profile_id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    return active_relationship is not None


def get_goals_for_viewer(db: Session, viewer: User, student_profile_id: str) -> StudentProfile:
    profile = db.get(StudentProfile, student_profile_id)
    if profile is None:
        raise StudentProfileError(status.HTTP_404_NOT_FOUND, "Student not found.")
    if profile.user_id != viewer.id and not (viewer.role == TRAINER_ROLE and trainer_has_access(db, viewer, profile.id)):
        raise StudentProfileError(status.HTTP_403_FORBIDDEN, "You cannot view this student's goals.")
    return profile


def current_questionnaire(db: Session, profile: StudentProfile) -> HealthQuestionnaire | None:
    return db.scalars(
        select(HealthQuestionnaire).where(
            HealthQuestionnaire.student_id == profile.id, HealthQuestionnaire.status == "CURRENT"
        )
    ).first()


def is_questionnaire_completed(db: Session, profile: StudentProfile) -> bool:
    return current_questionnaire(db, profile) is not None


def require_health_questionnaire(db: Session, profile: StudentProfile) -> None:
    """Reusable gate for specs 004 (send request) and 006 (access routine)."""
    if not is_questionnaire_completed(db, profile):
        raise StudentProfileError(status.HTTP_403_FORBIDDEN, "You must complete the health questionnaire first.")


def save_health_questionnaire(db: Session, user: User, payload: HealthQuestionnaireInput) -> HealthQuestionnaire:
    profile = get_or_create_profile(db, user)
    db.execute(
        update(HealthQuestionnaire)
        .where(HealthQuestionnaire.student_id == profile.id, HealthQuestionnaire.status == "CURRENT")
        .values(status="ARCHIVED")
    )
    questionnaire = HealthQuestionnaire(student_id=profile.id, completed_at=utc_now(), **payload.model_dump())
    db.add(questionnaire)
    db.commit()
    db.refresh(questionnaire)
    return questionnaire


def get_own_questionnaire(db: Session, user: User) -> HealthQuestionnaire:
    questionnaire = current_questionnaire(db, get_or_create_profile(db, user))
    if questionnaire is None:
        raise StudentProfileError(status.HTTP_404_NOT_FOUND, "Health questionnaire not completed yet.")
    return questionnaire


def get_questionnaire_for_viewer(db: Session, viewer: User, student_profile_id: str) -> HealthQuestionnaire:
    profile = get_goals_for_viewer(db, viewer, student_profile_id)
    questionnaire = current_questionnaire(db, profile)
    if questionnaire is None:
        raise StudentProfileError(status.HTTP_404_NOT_FOUND, "Health questionnaire not completed yet.")
    return questionnaire


def current_medical_clearance(db: Session, profile: StudentProfile) -> MedicalClearance | None:
    return db.scalars(
        select(MedicalClearance).where(
            MedicalClearance.student_id == profile.id, MedicalClearance.status == "CURRENT"
        )
    ).first()


def is_clearance_completed(db: Session, profile: StudentProfile) -> bool:
    return current_medical_clearance(db, profile) is not None


async def upload_medical_clearance(
    db: Session, user: User, file: UploadFile, issue_date: date
) -> MedicalClearance:
    require_student(user)
    profile = get_or_create_profile(db, user)

    try:
        file_path, file_size = await save_upload(profile.id, file)
    except StorageError as error:
        raise StudentProfileError(status.HTTP_400_BAD_REQUEST, error.message) from error

    db.execute(
        update(MedicalClearance)
        .where(MedicalClearance.student_id == profile.id, MedicalClearance.status == "CURRENT")
        .values(status="ARCHIVED")
    )
    clearance = MedicalClearance(
        student_id=profile.id,
        file_path=file_path,
        original_filename=file.filename or "apto",
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=file_size,
        issue_date=issue_date,
        status="CURRENT",
        created_at=utc_now(),
    )
    db.add(clearance)
    db.commit()
    db.refresh(clearance)
    return clearance


def get_own_clearance(db: Session, user: User) -> MedicalClearance:
    require_student(user)
    profile = get_or_create_profile(db, user)
    clearance = current_medical_clearance(db, profile)
    if clearance is None:
        raise StudentProfileError(status.HTTP_404_NOT_FOUND, "Certificado médico no encontrado.")
    return clearance


def get_clearance_for_download(
    db: Session, viewer: User, student_profile_id: str
) -> tuple[MedicalClearance, Path]:
    profile = db.get(StudentProfile, student_profile_id)
    if profile is None:
        raise StudentProfileError(status.HTTP_404_NOT_FOUND, "Student not found.")
    if profile.user_id != viewer.id and not (viewer.role == TRAINER_ROLE and trainer_has_access(db, viewer, profile.id)):
        raise StudentProfileError(status.HTTP_403_FORBIDDEN, "You cannot access this student's medical clearance.")
    clearance = current_medical_clearance(db, profile)
    if clearance is None:
        raise StudentProfileError(status.HTTP_404_NOT_FOUND, "No active medical clearance found.")
    try:
        path = open_upload(clearance.file_path)
    except StorageError as error:
        raise StudentProfileError(status.HTTP_404_NOT_FOUND, error.message) from error
    return clearance, path
