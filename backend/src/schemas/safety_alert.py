"""Schemas Pydantic para alertas de seguridad (US-29)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SafetyAlertType = Literal["PAIN", "REPEATED_DISCOMFORT", "EXCESSIVE_EFFORT"]
SafetyAlertStatus = Literal["PENDING", "REVIEWED"]
SafetyAlertAction = Literal["ADJUSTED_ROUTINE", "CONTACTED_STUDENT", "NO_ACTION"]


class SafetyAlertReviewRequest(BaseModel):
    action_taken: SafetyAlertAction
    trainer_note: str | None = Field(default=None, max_length=500)

    @field_validator("trainer_note", mode="before")
    @classmethod
    def normalize_trainer_note(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class SafetyAlertView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    relationship_id: str
    student_id: str
    student_name: str
    session_id: str | None = None
    session_day_name: str | None = None
    report_id: str | None = None
    exercise_id: str | None = None
    exercise_name: str | None = None
    alert_type: SafetyAlertType
    zone: str | None = None
    zone_display_name: str | None = None
    rpe: int | None = None
    status: SafetyAlertStatus
    action_taken: SafetyAlertAction | None = None
    trainer_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    student_seen_at: datetime | None = None


class StudentPainAlertReviewedNotice(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str | None = None
    session_day_name: str | None = None
    exercise_name: str | None = None
    zone: str | None = None
    zone_display_name: str | None = None
    action_taken: SafetyAlertAction
    trainer_note: str | None = None
    reviewed_at: datetime
