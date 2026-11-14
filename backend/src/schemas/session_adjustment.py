"""US-26: ajuste de la próxima sesión de un alumno a partir de su sesión finalizada."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from backend.src.schemas.routine_template import RoutineBlockInput


class AdjustmentInput(BaseModel):
    blocks: list[RoutineBlockInput] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def blank_note_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AdjustmentEntry(BaseModel):
    exercise_id: str
    exercise_name: str
    sets: int
    reps: str
    rest_seconds: int
    target_weight_kg: float | None = None


class AdjustmentBlock(BaseModel):
    name: str
    estimated_duration_minutes: int | None = None
    exercises: list[AdjustmentEntry]


class LoggedSet(BaseModel):
    set_number: int
    reps_completed: str
    weight_kg: float | None = None


class LoggedExercise(BaseModel):
    exercise_id: str
    exercise_name: str
    sets: list[LoggedSet]


class SessionPainZone(BaseModel):
    zone: str
    zone_label: str
    intensity: str  # DISCOMFORT, PAIN
    exercise_name: str | None = None
    context: str


class ReplacementRequest(BaseModel):
    original_exercise_id: str
    original_exercise_name: str
    replacement_exercise_name: str | None = None  # None: el alumno salteó el ejercicio


class AdjustmentView(BaseModel):
    id: str
    status: str  # PENDING, APPLIED
    note: str | None = None
    changed_exercise_ids: list[str]
    created_at: datetime
    applied_at: datetime | None = None


class SessionAdjustmentContext(BaseModel):
    session_id: str
    day_name: str
    started_at: datetime
    finished_at: datetime | None = None
    rpe: int | None = None
    logged_exercises: list[LoggedExercise]
    pain_zones: list[SessionPainZone]
    replacement_requests: list[ReplacementRequest]
    blocks: list[AdjustmentBlock]
    can_adjust: bool
    blocked_reason: str | None = None
    current_adjustment: AdjustmentView | None = None


class StudentAdjustmentNotice(BaseModel):
    day_name: str
    note: str | None = None
    exercise_ids: list[str]
    adjusted_at: datetime
