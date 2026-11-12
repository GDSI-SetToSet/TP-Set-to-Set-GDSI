from datetime import date, datetime
from typing import Any

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
