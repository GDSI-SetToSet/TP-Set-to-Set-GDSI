import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

PHONE_PATTERN = re.compile(r"^\+?[0-9]{8,15}$")


class TrainerProfileUpdate(BaseModel):
    full_name: str | None = None
    contact_phone: str | None = None
    specialty: str | None = None
    bio: str | None = None
    certifications: str | None = None

    @field_validator("full_name", "specialty", "bio", "certifications")
    @classmethod
    def reject_empty_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Este campo no puede estar vacío.")
        return value.strip() if value is not None else None

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is not None and not PHONE_PATTERN.fullmatch(value):
            raise ValueError("Ingresá un teléfono válido de 8 a 15 dígitos (puede iniciar con +).")
        return value


class TrainerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str | None
    contact_phone: str | None
    specialty: str | None
    status: str
    bio: str | None
    certifications: str | None
    max_students: int
    active_students_count: int = 0
    available_slots: int = 0
    created_at: datetime
    updated_at: datetime
