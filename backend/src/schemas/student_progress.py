"""US-65: evolución del alumno (solo lectura). Sin porcentajes ni estados de alerta: el frontend arma las frases."""

from datetime import date

from pydantic import BaseModel

from backend.src.schemas.trainer_student import AdherenceWeek, SetResult

MESSAGE_KEYS = (
    "weight_increased", "reps_increased", "no_change", "below_best", "bodyweight_reps_increased", "few_data",
)


class ProgressPeriod(BaseModel):
    key: str
    start: date | None = None
    end: date


class StreakSummary(BaseModel):
    current_weeks: int
    best_weeks: int


class ProgressSummary(BaseModel):
    improving_exercises_last_4w: int
    streak: StreakSummary
    records_in_period: int


class ExercisePoint(BaseModel):
    date: date
    weight: float | None = None
    reps: int
    target_weight: float | None = None
    is_pr: bool


class ExerciseEvolution(BaseModel):
    exercise_id: str
    name: str
    muscle_group: str
    metric: str  # "max_weight" | "max_reps"
    start: SetResult
    current: SetResult
    best: SetResult
    message_key: str
    weeks_without_change: int
    last_improvement_is_pr: bool
    points: list[ExercisePoint]


class RecordEntry(BaseModel):
    date: date
    exercise_id: str
    name: str
    weight: float | None = None
    reps: int
    previous: SetResult


class NewExercise(BaseModel):
    exercise_id: str
    name: str
    first_date: date


class NextExercise(BaseModel):
    exercise_id: str
    name: str
    last: SetResult | None = None  # None: primera vez
    target_weight: float | None = None
    reps: str
    sets: int
    adjusted_by_trainer: bool
    trainer_note: str | None = None


class NextSession(BaseModel):
    day_name: str
    trainer_feedback: str | None = None
    exercises: list[NextExercise]


class StudentProgress(BaseModel):
    period: ProgressPeriod
    muscle_group: str | None = None
    muscle_groups: list[str]
    has_sessions: bool
    summary: ProgressSummary
    exercises: list[ExerciseEvolution]
    consistency: list[AdherenceWeek]
    records: list[RecordEntry]
    new_exercises: list[NewExercise]
    next_session: NextSession | None = None


class TrainingStreak(BaseModel):
    """US-68: racha de semanas cumplidas (calculada, no persistida)."""

    has_routine: bool
    weekly_target: int
    current_weeks: int
    max_weeks: int
    this_week_sessions: int
    week_start: date
