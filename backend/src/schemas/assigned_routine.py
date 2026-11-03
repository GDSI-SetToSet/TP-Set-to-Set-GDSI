from datetime import datetime
from typing import Literal

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
    provider: Literal["gemini", "heuristic"] | None = Field(
        default=None,
        description="Proveedor de IA opcional ('gemini' o 'heuristic'). Si se omite, utiliza AI_PROVIDER.",
    )


class AssignedRoutineExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sets: int
    reps: str
    rest_seconds: int
    order_index: int
    adaptation_notes: str | None = None
    target_weight_kg: float | None = None
    exercise: ExerciseResponse


class AssignedRoutineBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    order_index: int
    estimated_duration_minutes: int | None = None
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
    trainer_name: str | None = None
    student_id: str
    template_id: str | None = None
    name: str
    duration_weeks: int
    intensity: str
    has_no_materials_alternative: bool = False
    status: str
    adaptation_summary: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    exercise_count: int
    days: list[AssignedRoutineDayResponse]


class TrainerAIRoutineResponse(AssignedRoutineResponse):
    """Rutina con IA tal como la ve el entrenador en "Mis rutinas"."""

    student_name: str = ""
    relationship_id: str = ""
    is_assigned: bool = False


class AssignedRoutineExerciseUpdateInput(BaseModel):
    exercise_id: str = Field(..., min_length=1)
    order_index: int = Field(default=0, ge=0)
    sets: int = Field(..., ge=1, le=20)
    reps: str = Field(..., min_length=1, max_length=50)
    rest_seconds: int = Field(default=60, ge=0, le=600)
    adaptation_notes: str | None = Field(default=None, max_length=255)
    target_weight_kg: float | None = Field(default=None, ge=0, le=9999.99)


class AssignedRoutineBlockUpdateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    order_index: int = Field(default=0, ge=0)
    estimated_duration_minutes: int | None = Field(default=None, ge=1, le=600)
    exercises: list[AssignedRoutineExerciseUpdateInput] = Field(default_factory=list)


class AssignedRoutineDayUpdateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    order_index: int = Field(default=0, ge=0)
    blocks: list[AssignedRoutineBlockUpdateInput] = Field(default_factory=list)


class AssignedRoutineUpdateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    duration_weeks: int = Field(..., ge=1, le=52)
    intensity: Literal["BAJA", "MEDIA", "ALTA", "EXIGENTE"]
    has_no_materials_alternative: bool = False
    days: list[AssignedRoutineDayUpdateInput] = Field(default_factory=list)
