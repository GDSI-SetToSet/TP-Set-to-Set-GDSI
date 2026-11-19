"""Esquemas de logros y felicitaciones (US-67)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

CONGRATULATION_MAX = 300
CONGRATULATION_MESSAGE = "Escribí la felicitación (hasta 300 caracteres)."


class CongratulationView(BaseModel):
    message: str
    trainer_name: str
    created_at: datetime
    seen_at: datetime | None


class AchievementItem(BaseModel):
    id: str
    code: str
    title: str
    description: str
    unlocked_at: datetime
    retroactive: bool
    pending_celebration: bool
    congratulation: CongratulationView | None


class LockedAchievement(BaseModel):
    code: str
    title: str
    description: str
    current: int
    target: int


class AchievementsOverview(BaseModel):
    unlocked: list[AchievementItem]
    locked: list[LockedAchievement]


class CongratulationCreate(BaseModel):
    message: str | None = Field(default=None, validate_default=True)

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, value: object) -> str:
        text = value.strip() if isinstance(value, str) else ""
        if not 1 <= len(text) <= CONGRATULATION_MAX:
            raise ValueError(CONGRATULATION_MESSAGE)
        return text
