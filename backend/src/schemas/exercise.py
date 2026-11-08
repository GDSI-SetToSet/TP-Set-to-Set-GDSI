from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from backend.src.core.constants import BODY_AREAS
from backend.src.core.video_urls import parse_video_url
from backend.src.models.exercise import VideoPlatform
from backend.src.schemas.trainer import REQUIRED_FIELD_MESSAGE

EXERCISE_CATEGORIES = ("FUERZA", "CARDIO", "MOVILIDAD", "FLEXIBILIDAD", "EQUILIBRIO")
NAME_MAX_LENGTH = 150
MUSCLE_MAX_LENGTH = 100
EQUIPMENT_MAX_LENGTH = 150
CUE_MAX_LENGTH = 2000
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
    technical_cues: str | None = Field(default=None, max_length=CUE_MAX_LENGTH)
    breathing_cues: str | None = Field(default=None, max_length=CUE_MAX_LENGTH)
    category: str | None = Field(default=None, validate_default=True)
    target_muscle_group: str | None = Field(default=None, validate_default=True)
    equipment_needed: str | None = Field(default=None, validate_default=True)
    has_no_materials_alternative: bool = False
    video_url: str | None = Field(default=None, max_length=500)
    contraindicated_zones: list[str] = Field(default_factory=list, max_length=20)

    _name = field_validator("name")(required_text(NAME_MAX_LENGTH))
    _description = field_validator("description")(required_text())
    _category = field_validator("category")(validate_category)
    _muscle = field_validator("target_muscle_group")(required_text(MUSCLE_MAX_LENGTH))
    _equipment = field_validator("equipment_needed")(required_text(EQUIPMENT_MAX_LENGTH))

    @field_validator("technical_cues", "breathing_cues")
    @classmethod
    def normalize_optional_cues(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("contraindicated_zones")
    @classmethod
    def normalize_zones(cls, value: list[str]) -> list[str]:
        canonical = {area.casefold(): area for area in BODY_AREAS}
        unknown = [zone for zone in value if zone.strip().casefold() not in canonical]
        if unknown:
            raise PydanticCustomError("zone", "Elegí zonas de la lista: {zones}", {"zones": ", ".join(unknown)})
        return sorted({canonical[zone.strip().casefold()] for zone in value})

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, value: str | None) -> str | None:
        parse_video_url(value)
        return value


class ExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trainer_id: str
    name: str
    description: str
    technical_cues: str | None
    breathing_cues: str | None
    category: str
    target_muscle_group: str
    equipment_needed: str
    has_no_materials_alternative: bool
    contraindicated_zones: list[str] = []
    video_url: str | None
    video_platform: VideoPlatform
    created_at: datetime
    updated_at: datetime
