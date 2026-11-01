from pydantic import BaseModel, Field, field_validator

from backend.src.schemas.routine_template import (
    RoutineTemplateInput,
    RoutineTemplateResponse,
    required_range,
)


class RoutineDraftInput(RoutineTemplateInput):
    draft_version: int = Field(ge=0)
    desired_weekly_volume: int | None = None

    @field_validator("desired_weekly_volume")
    @classmethod
    def weekly_volume_range(cls, value: int | None) -> int | None:
        return None if value is None else required_range(1, 7)(value)


class StudentRoutineResponse(BaseModel):
    routine: RoutineTemplateResponse
    draft: RoutineTemplateResponse | None = None
    draft_version: int
    desired_weekly_volume: int | None = None
    status: str


class DraftSavedResponse(BaseModel):
    draft_version: int
