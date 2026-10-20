"""Schemas Pydantic para el apto médico del alumno (US-43)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MedicalClearanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    issue_date: date
    status: str
    created_at: datetime
