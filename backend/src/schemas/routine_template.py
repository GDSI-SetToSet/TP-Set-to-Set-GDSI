from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from backend.src.schemas.exercise import ExerciseResponse, required_text
from backend.src.schemas.trainer import REQUIRED_FIELD_MESSAGE

ROUTINE_INTENSITIES = ("BAJA", "MEDIA", "ALTA", "EXIGENTE")
ROUTINE_MODALITIES = ("GYM", "HOME")
ROUTINE_NAME_MAX_LENGTH = 150
SECTION_NAME_MAX_LENGTH = 100
REPS_MAX_LENGTH = 50
INVALID_INTENSITY_MESSAGE = "Elegí una intensidad válida"
INVALID_MODALITY_MESSAGE = "Elegí una modalidad válida"


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


def validate_modality(value: str | None) -> str:
    if value is None or not value.strip():
        raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
    normalized = value.strip().upper()
    if normalized not in ROUTINE_MODALITIES:
        raise PydanticCustomError("modality", INVALID_MODALITY_MESSAGE)
    return normalized


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
    modality: str = "GYM"
    exercise_count: int
    days: list[RoutineDayResponse]


class RoutineModalityUpdate(BaseModel):
    modality: str | None = Field(default=None, validate_default=True)

    _modality = field_validator("modality")(validate_modality)


class WorkoutSessionStartInput(BaseModel):
    day_name: str | None = Field(default=None, validate_default=True)

    _day = field_validator("day_name")(required_text(SECTION_NAME_MAX_LENGTH))


class WorkoutSessionFinishInput(BaseModel):
    rpe: int | None = Field(default=None, ge=1, le=10, strict=True)


class WorkoutSessionRpeInput(BaseModel):
    rpe: int = Field(..., ge=1, le=10, strict=True)


class WorkoutSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    relationship_id: str
    routine_id: str
    day_name: str
    modality: str
    started_at: datetime
    finished_at: datetime | None = None
    rpe: int | None = None


class WorkoutSetLogInput(BaseModel):
    exercise_id: str | None = Field(default=None, validate_default=True)
    day_name: str | None = Field(default=None, validate_default=True)
    set_number: int | None = Field(default=None, validate_default=True)
    reps_completed: str | None = Field(default=None, validate_default=True)
    weight_kg: float | None = Field(default=None, ge=0, le=9999.99)
    duration_seconds: int | None = Field(default=None, ge=0, le=7200)
    session_id: str | None = None
    modality: str | None = None

    _exercise = field_validator("exercise_id")(required_text())
    _day = field_validator("day_name")(required_text(SECTION_NAME_MAX_LENGTH))
    _set = field_validator("set_number")(required_range(1, 20))
    _reps = field_validator("reps_completed")(required_text(REPS_MAX_LENGTH))

    @field_validator("modality")
    @classmethod
    def _check_optional_modality(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_modality(value)


class WorkoutSetLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    relationship_id: str
    routine_id: str
    day_name: str
    exercise_id: str
    exercise_name: str
    modality: str
    set_number: int
    reps_completed: str
    weight_kg: float | None = None
    duration_seconds: int | None = None
    session_id: str | None = None
    recorded_at: datetime
    is_personal_record: bool = False
    is_initial_pr: bool = False
    pr_previous_weight_kg: float | None = None


class PersonalRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    exercise_id: str
    exercise_name: str | None = None
    weight_kg: float
    reps_completed: str
    workout_set_log_id: str
    achieved_at: datetime


class RoutineAssignmentUpdate(BaseModel):
    routine_template_id: str | None


class RoutineAssignmentResponse(BaseModel):
    relationship_id: str
    routine_template_id: str | None
    warnings: list[str] = []


class RoutineAssignmentStudentResponse(BaseModel):
    relationship_id: str
    student_id: str
    student_name: str
    routine_template_id: str | None
    routine_name: str | None
