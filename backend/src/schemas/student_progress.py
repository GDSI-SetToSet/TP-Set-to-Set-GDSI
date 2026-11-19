"""US-65: evolución del alumno (solo lectura)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ProgressRange(BaseModel):
    from_: date = Field(alias="from")
    to: date
    is_default: bool

    model_config = ConfigDict(populate_by_name=True)


class LoadPoint(BaseModel):
    date: date
    weight_kg: float
    reps: str
    is_pr: bool


class ExerciseLoad(BaseModel):
    exercise_id: str
    name: str
    muscle_group: str
    has_trend: bool  # al menos 2 puntos
    points: list[LoadPoint]


class WeeklyVolume(BaseModel):
    week_start: date
    week_end: date
    volume_kg: float
    is_partial: bool


class WeekComparison(BaseModel):
    current_volume_kg: float
    previous_volume_kg: float
    delta_vs_previous_pct: float | None = None
    previous_avg_kg: float


class PersonalRecordEntry(BaseModel):
    exercise_id: str
    exercise_name: str
    weight_kg: float
    reps: str
    achieved_at: datetime
    previous_weight_kg: float | None = None
    is_initial: bool


class StudentProgress(BaseModel):
    range: ProgressRange
    muscle_groups: list[str]
    has_data: bool
    exercises: list[ExerciseLoad]
    weekly_volume: list[WeeklyVolume]
    week_comparison: WeekComparison
    personal_records: list[PersonalRecordEntry]


class TrainingStreak(BaseModel):
    """US-68: racha de semanas cumplidas (calculada, no persistida)."""

    has_routine: bool
    weekly_target: int
    current_weeks: int
    max_weeks: int
    this_week_sessions: int
    week_start: date
