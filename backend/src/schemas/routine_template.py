from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from backend.src.schemas.exercise import ExerciseResponse, required_text
from backend.src.schemas.trainer import REQUIRED_FIELD_MESSAGE

ROUTINE_INTENSITIES = ("BAJA", "MEDIA", "ALTA", "EXIGENTE")
ROUTINE_NAME_MAX_LENGTH = 150
SECTION_NAME_MAX_LENGTH = 100
REPS_MAX_LENGTH = 50
INVALID_INTENSITY_MESSAGE = "Elegí una intensidad válida"


def required_range(minimum: int, maximum: int) -> Callable[[int | None], int]:
    def validate(value: int | None) -> int:
        if value is None:
            raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
        if not minimum <= value <= maximum:
            raise PydanticCustomError(
                "range",
                "El valor debe estar entre {minimum} y {maximum}",
                {"minimum": minimum, "maximum": maximum},
            )
        return value

    return validate


def required_items(maximum: int) -> Callable[[list[Any] | None], list[Any]]:
    def validate(value: list[Any] | None) -> list[Any]:
        if not value:
            raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
        if len(value) > maximum:
            raise PydanticCustomError("too_many", "Se admiten hasta {maximum} elementos", {"maximum": maximum})
        return value

    return validate


def validate_intensity(value: str | None) -> str:
    if value is None or not value.strip():
        raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
    if value not in ROUTINE_INTENSITIES:
        raise PydanticCustomError("intensity", INVALID_INTENSITY_MESSAGE)
    return value


class RoutineExerciseInput(BaseModel):
    exercise_id: str | None = Field(default=None, validate_default=True)
    sets: int | None = Field(default=None, validate_default=True)
    reps: str | None = Field(default=None, validate_default=True)
    rest_seconds: int | None = Field(default=None, validate_default=True)
    target_weight_kg: float | None = Field(default=None, ge=0, le=9999.99)

    _exercise = field_validator("exercise_id")(required_text())
    _sets = field_validator("sets")(required_range(1, 20))
    _reps = field_validator("reps")(required_text(REPS_MAX_LENGTH))
    _rest = field_validator("rest_seconds")(required_range(0, 600))


class RoutineBlockInput(BaseModel):
    name: str | None = Field(default=None, validate_default=True)
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=600)
    exercises: list[RoutineExerciseInput] | None = Field(default=None, validate_default=True)

    _name = field_validator("name")(required_text(SECTION_NAME_MAX_LENGTH))
    _exercises = field_validator("exercises")(required_items(30))


class RoutineDayInput(BaseModel):
    name: str | None = Field(default=None, validate_default=True)
    blocks: list[RoutineBlockInput] | None = Field(default=None, validate_default=True)

    _name = field_validator("name")(required_text(SECTION_NAME_MAX_LENGTH))
    _blocks = field_validator("blocks")(required_items(10))


class RoutineTemplateInput(BaseModel):
    name: str | None = Field(default=None, validate_default=True)
    duration_weeks: int | None = Field(default=None, validate_default=True)
    intensity: str | None = Field(default=None, validate_default=True)
    has_no_materials_alternative: bool = False
    days: list[RoutineDayInput] | None = Field(default=None, validate_default=True)

    _name = field_validator("name")(required_text(ROUTINE_NAME_MAX_LENGTH))
    _duration = field_validator("duration_weeks")(required_range(1, 52))
    _intensity = field_validator("intensity")(validate_intensity)
    _days = field_validator("days")(required_items(7))


class RoutineExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sets: int
    reps: str
    rest_seconds: int
    target_weight_kg: float | None = None
    exercise: ExerciseResponse


class RoutineBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    estimated_duration_minutes: int | None = None
    exercises: list[RoutineExerciseResponse]


class RoutineDayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    blocks: list[RoutineBlockResponse]


class RoutineTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trainer_id: str
    trainer_name: str | None
    name: str
    duration_weeks: int
    intensity: str
    has_no_materials_alternative: bool
    exercise_count: int
    days: list[RoutineDayResponse]


class RoutineAssignmentUpdate(BaseModel):
    routine_template_id: str | None


class RoutineAssignmentResponse(BaseModel):
    relationship_id: str
    routine_template_id: str | None


class RoutineAssignmentStudentResponse(BaseModel):
    relationship_id: str
    student_id: str
    student_name: str
    routine_template_id: str | None
    routine_name: str | None
