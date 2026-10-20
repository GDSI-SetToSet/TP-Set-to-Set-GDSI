from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProtectedZonesUpdate(BaseModel):
    zones: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("zones")
    @classmethod
    def normalize_zones(cls, zones: list[str]) -> list[str]:
        normalized = [zone.strip() for zone in zones]
        if any(not zone for zone in normalized):
            raise ValueError("Protected zones cannot be empty.")
        if any(len(zone) > 80 for zone in normalized):
            raise ValueError("Protected zones cannot exceed 80 characters.")
        if len({zone.casefold() for zone in normalized}) != len(normalized):
            raise ValueError("Protected zones must not repeat.")
        return normalized


class ProtectedZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    body_area: str
    created_at: datetime


class ProtectedZonesResponse(BaseModel):
    zones: list[ProtectedZoneResponse]
