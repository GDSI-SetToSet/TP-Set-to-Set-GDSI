from pydantic import BaseModel, Field

from backend.src.schemas.safe_variant import SafeVariantRef


class Alternative(BaseModel):
    exercise_id: str
    name: str
    equipment_needed: str
    variant: SafeVariantRef | None = None


class AlternativesResponse(BaseModel):
    alternatives: list[Alternative]
    can_skip: bool


class ReplacementInput(BaseModel):
    day_name: str = Field(min_length=1, max_length=100)
    original_exercise_id: str
    replacement_exercise_id: str | None = None  # None = el alumno saltea el ejercicio


class ReplacementResponse(BaseModel):
    original_exercise_id: str
    replacement_exercise_id: str | None
