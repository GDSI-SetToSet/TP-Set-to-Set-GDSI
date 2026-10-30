from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from backend.src.schemas.trainer import REQUIRED_FIELD_MESSAGE

EXERCISE_CATEGORIES = ("FUERZA", "CARDIO", "MOVILIDAD", "FLEXIBILIDAD", "EQUILIBRIO")
NAME_MAX_LENGTH = 150
MUSCLE_MAX_LENGTH = 100
EQUIPMENT_MAX_LENGTH = 150
INVALID_CATEGORY_MESSAGE = "Elegí una categoría válida"


def required_text(max_length: int | None = None) -> Callable[[str | None], str]:
    def validate(value: str | None) -> str:
        if value is None or not value.strip():
            raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
        text = value.strip()
        if max_length is not None and len(text) > max_length:
            raise PydanticCustomError(
                "too_long", "Este campo admite hasta {max_length} caracteres", {"max_length": max_length}
            )
        return text

    return validate


def validate_category(value: str | None) -> str:
    if value is None or not value.strip():
        raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
    if value not in EXERCISE_CATEGORIES:
        raise PydanticCustomError("category", INVALID_CATEGORY_MESSAGE)
    return value


class ExerciseInput(BaseModel):
    name: str | None = Field(default=None, validate_default=True)
    description: str | None = Field(default=None, validate_default=True)
    category: str | None = Field(default=None, validate_default=True)
    target_muscle_group: str | None = Field(default=None, validate_default=True)
    equipment_needed: str | None = Field(default=None, validate_default=True)
    has_no_materials_alternative: bool = False

    _name = field_validator("name")(required_text(NAME_MAX_LENGTH))
    _description = field_validator("description")(required_text())
    _category = field_validator("category")(validate_category)
    _muscle = field_validator("target_muscle_group")(required_text(MUSCLE_MAX_LENGTH))
    _equipment = field_validator("equipment_needed")(required_text(EQUIPMENT_MAX_LENGTH))


class ExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trainer_id: str
    name: str
    description: str
    category: str
    target_muscle_group: str
    equipment_needed: str
    has_no_materials_alternative: bool
    created_at: datetime
    updated_at: datetime
