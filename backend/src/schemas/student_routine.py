from pydantic import BaseModel, Field, field_validator

from backend.src.schemas.routine_template import (
    RoutineTemplateInput,
    RoutineTemplateResponse,
    required_range,
)
from backend.src.schemas.safe_variant import SafeVariantRef


class RoutineDraftInput(RoutineTemplateInput):
    draft_version: int = Field(ge=0)
    desired_weekly_volume: int | None = None

    @field_validator("desired_weekly_volume")
    @classmethod
    def weekly_volume_range(cls, value: int | None) -> int | None:
        return None if value is None else required_range(1, 7)(value)


class RoutineConflict(BaseModel):
    field: str
    message: str
    safe_variant: SafeVariantRef | None = None


class StudentRoutineResponse(BaseModel):
    routine: RoutineTemplateResponse
    draft: RoutineTemplateResponse | None = None
    draft_version: int
    desired_weekly_volume: int | None = None
    status: str
    conflicts: list[RoutineConflict] = []


class DraftSavedResponse(BaseModel):
    draft_version: int
