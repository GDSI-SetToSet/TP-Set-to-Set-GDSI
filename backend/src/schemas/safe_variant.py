from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _clean_zones(zones: list[str]) -> list[str]:
    cleaned = list(dict.fromkeys(z.strip().lower() for z in zones if z.strip()))
    if not cleaned:
        raise ValueError("Indicá al menos una zona cubierta.")
    return cleaned


class SafeVariantZones(BaseModel):
    covered_zones: list[str] = Field(min_length=1, max_length=20)

    @field_validator("covered_zones")
    @classmethod
    def clean(cls, value: list[str]) -> list[str]:
        return _clean_zones(value)


class SafeVariantInput(SafeVariantZones):
    variant_exercise_id: str


class SafeVariantResponse(BaseModel):
    id: str
    variant_exercise_id: str
    variant_name: str
    covered_zones: list[str]


class SafeVariantRef(BaseModel):
    exercise_id: str
    name: str


class SafeVariantDetail(SafeVariantRef):
    description: str
    video_url: str | None = None
    video_platform: str


class SafeVariantResolution(BaseModel):
    status: Literal["SAFE", "VARIANT", "BLOCKED"]
    variant: SafeVariantDetail | None = None
    message: str | None = None
    can_skip: bool = False
