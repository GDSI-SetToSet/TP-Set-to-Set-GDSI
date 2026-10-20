import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")

class StudentProfileUpdate(BaseModel):
    full_name: str | None = None
    birth_date: datetime | None = None
    contact_phone: str | None = None
    profile_picture: str | None = None
    bio: str | None = None

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is not None and not PHONE_PATTERN.fullmatch(value):
            raise ValueError("The contact phone must contain at least 10 numeric characters.")
        return value

class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str | None
    birth_date: datetime | None
    contact_phone: str | None
    profile_picture: str | None
    bio: str | None
    status: str
    created_at: datetime
    updated_at: datetime