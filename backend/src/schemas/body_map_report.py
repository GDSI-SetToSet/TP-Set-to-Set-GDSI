from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.src.core.constants import BODY_AREAS, canonical_zone_key

IntensityLevel = Literal["NORMAL", "DISCOMFORT", "PAIN"]
ReportContext = Literal["POST_SESSION", "IN_EXERCISE"]
ActionTaken = Literal["NONE", "VARIANT_OFFERED", "VARIANT_ACCEPTED", "EXERCISE_SKIPPED"]

ZONE_DISPLAY_NAMES: dict[str, str] = {
    "Neck": "Cuello",
    "Shoulder": "Hombro",
    "Elbow": "Codo",
    "Wrist and hand": "Muñeca y mano",
    "Upper back": "Espalda alta",
    "Lower back": "Espalda baja",
    "Hip": "Cadera",
    "Knee": "Rodilla",
    "Ankle and foot": "Tobillo y pie",
}

CANONICAL_ZONE_BY_KEY: dict[str, str] = {
    canonical_zone_key(area): area for area in BODY_AREAS
}


def normalize_zone_name(value: str) -> str:
    key = canonical_zone_key(value)
    if key in CANONICAL_ZONE_BY_KEY:
        return CANONICAL_ZONE_BY_KEY[key]
    # Si coincide exactamente con alguna de BODY_AREAS sin modificar
    for area in BODY_AREAS:
        if area.lower() == value.strip().lower():
            return area
    raise ValueError(f"Zona corporal no reconocida: '{value}'. Las zonas válidas son: {', '.join(BODY_AREAS)}.")


class ReportZoneInput(BaseModel):
    zone: str
    intensity: IntensityLevel

    @field_validator("zone")
    @classmethod
    def validate_zone(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La zona corporal no puede estar vacía.")
        return normalize_zone_name(v)


class ReportZoneOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    zone: str
    zone_display: str
    intensity: IntensityLevel
    created_at: datetime


class SafeVariantSnippet(BaseModel):
    exercise_id: str
    name: str
    description: str | None = None
    video_url: str | None = None
    video_platform: str | None = None


class SafeVariantEvaluation(BaseModel):
    status: Literal["SAFE", "VARIANT", "BLOCKED"]
    variant: SafeVariantSnippet | None = None
    message: str | None = None
    can_skip: bool = False


class BodyMapReportCreate(BaseModel):
    session_id: str | None = None
    exercise_id: str | None = None
    context: ReportContext
    action_taken: ActionTaken | None = None
    idempotency_key: Annotated[str | None, Field(max_length=64)] = None
    zones: list[ReportZoneInput]

    @field_validator("zones")
    @classmethod
    def validate_zones_non_empty_and_unique(cls, zones: list[ReportZoneInput]) -> list[ReportZoneInput]:
        if not zones:
            raise ValueError("El reporte debe incluir al menos una zona corporal.")
        seen_zones: set[str] = set()
        for item in zones:
            if item.zone in seen_zones:
                raise ValueError(f"La zona '{item.zone}' se encuentra repetida en el mismo reporte.")
            seen_zones.add(item.zone)
        return zones


class BodyMapReportActionUpdate(BaseModel):
    action_taken: ActionTaken


class BodyMapReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_id: str
    session_id: str | None = None
    exercise_id: str | None = None
    exercise_name: str | None = None
    context: str
    action_taken: str | None = None
    created_at: datetime
    zones: list[ReportZoneOutput]
    safe_variant: SafeVariantEvaluation | None = None


class BodyMapZoneHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_id: str
    zone: str
    zone_display: str
    intensity: IntensityLevel
    created_at: datetime
    session_id: str | None = None
    session_day_name: str | None = None
    exercise_id: str | None = None
    exercise_name: str | None = None
    context: str
    action_taken: str | None = None
