from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class TrainerStudentListItem(BaseModel):
    relationship_id: str
    student_id: str
    full_name: str
    profile_status: str
    package_title: str | None = None
    routine_name: str | None = None
    has_activity: bool
    unreviewed_alert_count: int | None = None


class TrainerStudentRelationship(BaseModel):
    id: str
    status: str
    start_date: date
    package_title: str | None = None
    agreed_monthly_price: float
    agreed_currency: str


class TrainerStudentProfile(BaseModel):
    id: str
    first_name: str | None
    last_name: str | None
    birth_date: datetime | None
    contact_phone: str | None
    profile_picture: str | None
    bio: str | None
    status: str


class TrainerStudentGoals(BaseModel):
    fitness_goals: list[str]
    personal_motivation: str | None


class TrainerStudentLimitations(BaseModel):
    protected_zones: list[str]
    safety_indicators: list[str]


class TrainerStudentRoutine(BaseModel):
    id: str
    name: str
    source: str


class TrainerStudentMetrics(BaseModel):
    finished_sessions: int
    last_session_at: datetime | None = None
    logged_sets: int
    last_rpe: int | None = None
    last_tonnage_kg: float | None = None


class TrainerStudentDetail(BaseModel):
    relationship: TrainerStudentRelationship
    profile: TrainerStudentProfile
    goals: TrainerStudentGoals
    limitations: TrainerStudentLimitations
    routine: TrainerStudentRoutine | None = None
    metrics: TrainerStudentMetrics
    available_existing_views: dict[str, Any]


class DailyRoutineSet(BaseModel):
    set_number: int
    reps_completed: str
    weight_kg: float | None = None
    duration_seconds: int | None = None
    recorded_at: datetime


class DailyRoutineExercise(BaseModel):
    exercise_id: str
    exercise_name: str
    sets: list[DailyRoutineSet]


class DailyRoutineSession(BaseModel):
    id: str
    day_name: str
    modality: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    rpe: int | None = None


class DailyRoutineItem(BaseModel):
    relationship_id: str
    student_id: str
    student_name: str
    routine_name: str | None = None
    status: str  # NOT_STARTED, TRAINING, FINISHED
    session: DailyRoutineSession | None = None
    exercises: list[DailyRoutineExercise] = []


class AbandonmentRiskItem(BaseModel):
    relationship_id: str
    student_id: str
    student_name: str
    at_risk: bool
    reason: str | None = None  # MISSED_TRAININGS, INACTIVE_TWO_WEEKS
    weekly_trainings: int
    days_without_report: int
    missed_trainings: int
    last_report_at: datetime | None = None


class PlannedMetrics(BaseModel):
    sets: int
    reps: str
    target_weight_kg: float | None = None


class PerformedMetrics(BaseModel):
    sets_completed: int
    reps: list[str]
    max_weight_kg: float | None = None
    volume_kg: float
    total_duration_seconds: int | None = None


class ExerciseComparison(BaseModel):
    exercise_id: str
    exercise_name: str
    replaced_exercise_name: str | None = None
    planned: PlannedMetrics | None = None
    performed: PerformedMetrics | None = None
    previous: PerformedMetrics | None = None


class SessionComparison(BaseModel):
    """US-24: sesión finalizada vs lo planificado y vs la sesión previa del mismo día de rutina."""

    session: DailyRoutineSession
    previous_session: DailyRoutineSession | None = None
    planned_duration_seconds: int | None = None
    volume_kg: float
    previous_volume_kg: float | None = None
    exercises: list[ExerciseComparison]


TrafficLight = Literal["green", "yellow", "red"]
ExerciseStatus = Literal["progressing", "stalled", "declined", "unchanged", "few_data", "no_metric"]


class EvolutionPeriod(BaseModel):
    key: Literal["4w", "12w", "all"]
    start: date | None = None
    end: date


class SetResult(BaseModel):
    weight: float | None = None  # None sin carga (peso corporal)
    reps: int | None = None


class LastImprovement(BaseModel):
    date: date
    is_pr: bool


class ExercisePoint(BaseModel):
    key: str
    period_start: date
    period_end: date
    weight: float | None = None
    reps: int | None = None
    target_weight: float | None = None
    rpe: int | None = None
    is_pr: bool
    is_partial: bool  # pertenece a la semana en curso


class ExerciseProgress(BaseModel):
    exercise_id: str
    name: str
    muscle_group: str
    metric: Literal["max_weight", "max_reps", "none"]
    start: SetResult | None = None
    current: SetResult | None = None
    change_pct: float | None = None
    last_improvement: LastImprovement | None = None
    status: ExerciseStatus
    points: list[ExercisePoint]


class AdherenceWeek(BaseModel):
    period_start: date
    period_end: date
    scheduled: int
    completed: int
    is_partial: bool


class MostSkipped(BaseModel):
    exercise_id: str
    name: str
    completion_pct: int
    skip_count: int
    main_reason: Literal["replacement_requested"] | None = None


class RpePoint(BaseModel):
    key: str
    period_start: date
    period_end: date
    rpe: float | None = None
    has_report: bool
    trainer_feedback: str | None = None
    is_partial: bool


class MuscleGroupSets(BaseModel):
    muscle_group: str
    avg_completed_per_week: float
    avg_scheduled_per_week: float


class ReviewItem(BaseModel):
    type: Literal["exercise_declined", "exercise_stalled", "fatigue", "excessive_effort", "exercise_skipped", "week_without_training"]
    exercise_id: str | None = None
    label: str


class ProgressSummary(BaseModel):
    improving: int
    with_data: int
    status: TrafficLight | None = None


class AdherenceSummary(BaseModel):
    completed_sessions: int
    scheduled_sessions: int
    pct: int | None = None
    sets_completion_pct: int | None = None
    status: TrafficLight | None = None


class EffortSummary(BaseModel):
    avg_rpe_last_4: float | None = None
    trend: Literal["rising", "stable", "falling"] | None = None
    message_key: Literal[
        "excessive_effort", "fatigue", "room_for_more", "progressing_effort_rising", "progressing_with_margin"
    ] | None = None
    status: TrafficLight | None = None


class ReviewSummary(BaseModel):
    count: int
    status: TrafficLight


class EvolutionSummary(BaseModel):
    progress: ProgressSummary
    adherence: AdherenceSummary
    effort: EffortSummary
    to_review: ReviewSummary


class TrainingEvolution(BaseModel):
    """US-30: progreso del alumno: progresión por ejercicio, adherencia, esfuerzo y puntos a revisar."""

    period: EvolutionPeriod
    group_by: Literal["session", "week"]
    muscle_group: str | None = None
    muscle_groups: list[str]  # de todo el historial, para el filtro
    has_sessions: bool  # el alumno finalizó alguna sesión alguna vez
    summary: EvolutionSummary
    exercises: list[ExerciseProgress]
    adherence: list[AdherenceWeek]
    most_skipped: list[MostSkipped]
    rpe: list[RpePoint]
    sets_by_muscle_group: list[MuscleGroupSets]
    to_review: list[ReviewItem]
