from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.body_map_report import (
    BodyMapReportActionUpdate,
    BodyMapReportCreate,
    BodyMapReportResponse,
    BodyMapZoneHistoryItem,
)
from backend.src.services.body_map_report_service import (
    BodyMapReportError,
    create_body_map_report,
    list_student_body_map_reports,
    list_student_zone_history,
    list_trainer_student_body_map_reports,
    list_trainer_student_zone_history,
    update_report_action,
)

router = APIRouter(prefix=API_V1_PREFIX, tags=["body-map-reports"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def _handle_service_error(err: BodyMapReportError) -> None:
    raise HTTPException(status_code=err.status_code, detail=err.detail) from err


@router.post(
    "/body-map-reports",
    response_model=BodyMapReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    payload: BodyMapReportCreate, user: CurrentUser, db: DbDep
) -> BodyMapReportResponse:
    try:
        return create_body_map_report(db, user, payload)
    except BodyMapReportError as err:
        _handle_service_error(err)


@router.patch(
    "/body-map-reports/{report_id}/action",
    response_model=BodyMapReportResponse,
)
def update_action(
    report_id: str,
    payload: BodyMapReportActionUpdate,
    user: CurrentUser,
    db: DbDep,
) -> BodyMapReportResponse:
    try:
        return update_report_action(db, user, report_id, payload.action_taken)
    except BodyMapReportError as err:
        _handle_service_error(err)


@router.get(
    "/students/me/body-map-reports",
    response_model=list[BodyMapReportResponse],
)
def get_student_reports(
    user: CurrentUser,
    db: DbDep,
    zone: str | None = Query(None, description="Filtrar por zona corporal"),
    intensity: str | None = Query(None, description="Filtrar por intensidad (NORMAL, DISCOMFORT, PAIN)"),
    session_id: str | None = Query(None, description="Filtrar por sesión de entrenamiento"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[BodyMapReportResponse]:
    try:
        return list_student_body_map_reports(
            db, user, zone=zone, intensity=intensity, session_id=session_id, limit=limit, offset=offset
        )
    except BodyMapReportError as err:
        _handle_service_error(err)


@router.get(
    "/students/me/body-map-reports/by-zone",
    response_model=list[BodyMapZoneHistoryItem],
)
def get_student_zone_history(
    user: CurrentUser,
    db: DbDep,
    zone: str | None = Query(None, description="Filtrar por zona"),
    intensity: str | None = Query(None, description="Filtrar por intensidad"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[BodyMapZoneHistoryItem]:
    try:
        return list_student_zone_history(
            db, user, zone=zone, intensity=intensity, limit=limit, offset=offset
        )
    except BodyMapReportError as err:
        _handle_service_error(err)


@router.get(
    "/trainers/me/students/{student_id}/body-map-reports",
    response_model=list[BodyMapReportResponse],
)
def get_trainer_student_reports(
    student_id: str,
    user: CurrentUser,
    db: DbDep,
    zone: str | None = Query(None),
    intensity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[BodyMapReportResponse]:
    try:
        return list_trainer_student_body_map_reports(
            db, user, student_id, zone=zone, intensity=intensity, limit=limit, offset=offset
        )
    except BodyMapReportError as err:
        _handle_service_error(err)


@router.get(
    "/trainers/me/students/{student_id}/body-map-reports/by-zone",
    response_model=list[BodyMapZoneHistoryItem],
)
def get_trainer_student_zone_history(
    student_id: str,
    user: CurrentUser,
    db: DbDep,
    zone: str | None = Query(None),
    intensity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[BodyMapZoneHistoryItem]:
    try:
        return list_trainer_student_zone_history(
            db, user, student_id, zone=zone, intensity=intensity, limit=limit, offset=offset
        )
    except BodyMapReportError as err:
        _handle_service_error(err)
