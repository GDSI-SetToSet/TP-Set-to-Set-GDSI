from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.student_profile import StudentProfile
from backend.src.models.user import User
from backend.src.schemas.medical_clearance import MedicalClearanceResponse
from backend.src.schemas.protected_zone import (
    ProtectedZonesResponse,
    ProtectedZonesUpdate,
)
from backend.src.schemas.safety_alert import StudentPainAlertReviewedNotice
from backend.src.schemas.student import (
    StudentGoalsResponse,
    StudentProfileResponse,
    StudentProfileUpdate,
)
from backend.src.schemas.student_health import (
    HealthQuestionnaireInput,
    HealthQuestionnaireResponse,
)
from backend.src.services.safety_alert_service import (
    SafetyAlertError,
    list_student_reviewed_pain_notices,
    mark_safety_alert_seen,
)
from backend.src.services.student_service import (
    StudentProfileError,
    get_clearance_for_download,
    get_goals_for_viewer,
    get_or_create_profile,
    get_own_clearance,
    get_own_protected_zones,
    get_own_questionnaire,
    get_questionnaire_for_viewer,
    is_clearance_completed,
    is_questionnaire_completed,
    replace_own_protected_zones,
    save_health_questionnaire,
    update_profile,
    upload_medical_clearance,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/students", tags=["students"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def profile_response(profile: StudentProfile, db: Session) -> StudentProfileResponse:
    response = StudentProfileResponse.model_validate(profile)
    response.health_questionnaire_completed = is_questionnaire_completed(db, profile)
    response.medical_clearance_completed = is_clearance_completed(db, profile)
    return response


def handle_error(error: StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


def handle_safety_alert_error(error: SafetyAlertError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/me/profile", response_model=StudentProfileResponse)
def own_profile(user: CurrentUser, db: DbDep) -> StudentProfileResponse:
    try:
        return profile_response(get_or_create_profile(db, user), db)
    except StudentProfileError as error:
        handle_error(error)


@router.put("/me/profile", response_model=StudentProfileResponse)
def save_own_profile(payload: StudentProfileUpdate, user: CurrentUser, db: DbDep) -> StudentProfileResponse:
    try:
        return profile_response(update_profile(db, user, payload), db)
    except StudentProfileError as error:
        handle_error(error)


@router.get("/me/protected-zones", response_model=ProtectedZonesResponse)
def own_protected_zones(user: CurrentUser, db: DbDep) -> ProtectedZonesResponse:
    try:
        return ProtectedZonesResponse.model_validate({"zones": get_own_protected_zones(db, user)})
    except StudentProfileError as error:
        handle_error(error)


@router.put("/me/protected-zones", response_model=ProtectedZonesResponse)
def save_own_protected_zones(
    payload: ProtectedZonesUpdate, user: CurrentUser, db: DbDep
) -> ProtectedZonesResponse:
    try:
        zones = replace_own_protected_zones(db, user, payload)
        return ProtectedZonesResponse.model_validate({"zones": zones})
    except StudentProfileError as error:
        handle_error(error)


@router.get("/me/health-questionnaire", response_model=HealthQuestionnaireResponse)
def own_questionnaire(user: CurrentUser, db: DbDep) -> HealthQuestionnaireResponse:
    try:
        return HealthQuestionnaireResponse.model_validate(get_own_questionnaire(db, user))
    except StudentProfileError as error:
        handle_error(error)


@router.post("/me/health-questionnaire", response_model=HealthQuestionnaireResponse, status_code=status.HTTP_201_CREATED)
def save_own_questionnaire(payload: HealthQuestionnaireInput, user: CurrentUser, db: DbDep) -> HealthQuestionnaireResponse:
    try:
        return HealthQuestionnaireResponse.model_validate(save_health_questionnaire(db, user, payload))
    except StudentProfileError as error:
        handle_error(error)


@router.get("/me/medical-clearance", response_model=MedicalClearanceResponse)
def own_medical_clearance(user: CurrentUser, db: DbDep) -> MedicalClearanceResponse:
    try:
        return MedicalClearanceResponse.model_validate(get_own_clearance(db, user))
    except StudentProfileError as error:
        handle_error(error)


@router.post("/me/medical-clearance", response_model=MedicalClearanceResponse, status_code=status.HTTP_201_CREATED)
async def upload_own_medical_clearance(
    user: CurrentUser,
    db: DbDep,
    file: Annotated[UploadFile, File()],
    issue_date: Annotated[date, Form()],
) -> MedicalClearanceResponse:
    try:
        clearance = await upload_medical_clearance(db, user, file, issue_date)
        return MedicalClearanceResponse.model_validate(clearance)
    except StudentProfileError as error:
        handle_error(error)


@router.get(
    "/me/safety-alerts/reviewed-notices",
    response_model=list[StudentPainAlertReviewedNotice],
)
def own_reviewed_pain_alert_notices(
    user: CurrentUser, db: DbDep
) -> list[StudentPainAlertReviewedNotice]:
    """US-29 (CA-5): avisos de reportes de dolor revisados y pendientes de ver en la próxima sesión."""
    try:
        return list_student_reviewed_pain_notices(db, user)
    except SafetyAlertError as error:
        handle_safety_alert_error(error)


@router.post(
    "/me/safety-alerts/{alert_id}/seen",
    response_model=StudentPainAlertReviewedNotice,
)
def mark_own_safety_alert_notice_seen(
    alert_id: str, user: CurrentUser, db: DbDep
) -> StudentPainAlertReviewedNotice:
    """US-29 (CA-5): registra la visualización única de un aviso de dolor revisado."""
    try:
        return mark_safety_alert_seen(db, user, alert_id)
    except SafetyAlertError as error:
        handle_safety_alert_error(error)


@router.get("/{student_id}/medical-clearance/download")
def download_student_medical_clearance(student_id: str, user: CurrentUser, db: DbDep):
    try:
        clearance, path = get_clearance_for_download(db, user, student_id)
        return FileResponse(
            path=str(path),
            media_type=clearance.mime_type,
            filename=clearance.original_filename,
        )
    except StudentProfileError as error:
        handle_error(error)


@router.get("/{student_id}/health-questionnaire", response_model=HealthQuestionnaireResponse)
def student_questionnaire(student_id: str, user: CurrentUser, db: DbDep) -> HealthQuestionnaireResponse:
    try:
        return HealthQuestionnaireResponse.model_validate(get_questionnaire_for_viewer(db, user, student_id))
    except StudentProfileError as error:
        handle_error(error)


@router.get("/{student_id}/goals", response_model=StudentGoalsResponse)
def student_goals(student_id: str, user: CurrentUser, db: DbDep) -> StudentGoalsResponse:
    try:
        return StudentGoalsResponse.model_validate(get_goals_for_viewer(db, user, student_id))
    except StudentProfileError as error:
        handle_error(error)
