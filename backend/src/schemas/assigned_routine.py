from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.src.schemas.exercise import ExerciseResponse


class ActiveStudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    relationship_id: str
    student_id: str
    full_name: str
    age: int | None = None
    fitness_goals: list[str] = Field(default_factory=list)
    protected_zones_count: int = 0


class GenerateAIRoutineInput(BaseModel):
    student_id: str = Field(..., min_length=1, description="ID del perfil del alumno")
    template_id: str = Field(..., min_length=1, description="ID de la plantilla genérica")


class AssignedRoutineExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sets: int
    reps: str
    rest_seconds: int
    order_index: int
    adaptation_notes: str | None = None
    exercise: ExerciseResponse


class AssignedRoutineBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    order_index: int
    exercises: list[AssignedRoutineExerciseResponse]


class AssignedRoutineDayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    order_index: int
    blocks: list[AssignedRoutineBlockResponse]


class AssignedRoutineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trainer_id: str
    student_id: str
    template_id: str | None = None
    name: str
    duration_weeks: int
    intensity: str
    status: str
    adaptation_summary: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    exercise_count: int
    days: list[AssignedRoutineDayResponse]
