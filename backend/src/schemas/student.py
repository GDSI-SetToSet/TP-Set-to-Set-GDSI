import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")

FitnessGoal = Literal[
    "fuerza", "hipertrofia", "resistencia", "perdida_de_peso", "salud_general", "movilidad_rehabilitacion"
]

class StudentProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    birth_date: datetime | None = None
    contact_phone: str | None = None
    profile_picture: str | None = None
    bio: str | None = None
    fitness_goals: list[FitnessGoal] = Field(default_factory=list)
    personal_motivation: str | None = None

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is not None and not PHONE_PATTERN.fullmatch(value):
            raise ValueError("The contact phone must have 10 to 15 digits, with an optional leading '+'.")
        return value

    @field_validator("fitness_goals")
    @classmethod
    def validate_unique_goals(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Fitness goals must not repeat.")
        return value

class StudentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    first_name: str | None
    last_name: str | None
    birth_date: datetime | None
    contact_phone: str | None
    profile_picture: str | None
    bio: str | None
    fitness_goals: list[str]
    personal_motivation: str | None
    health_questionnaire_completed: bool = False
    medical_clearance_completed: bool = False
    status: str
    created_at: datetime
    updated_at: datetime


class StudentGoalsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fitness_goals: list[str]
    personal_motivation: str | None
