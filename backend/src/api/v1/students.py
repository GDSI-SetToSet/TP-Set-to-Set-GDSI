from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.student_profile import StudentProfile
from backend.src.models.user import User
from backend.src.schemas.protected_zone import ProtectedZonesResponse, ProtectedZonesUpdate
from backend.src.schemas.student import (
    StudentGoalsResponse,
    StudentProfileResponse,
    StudentProfileUpdate,
)
from backend.src.schemas.student_health import (
    HealthQuestionnaireInput,
    HealthQuestionnaireResponse,
)
from backend.src.services.student_service import (
    StudentProfileError,
    get_goals_for_viewer,
    get_or_create_profile,
    get_own_protected_zones,
    get_own_questionnaire,
    get_questionnaire_for_viewer,
    is_questionnaire_completed,
    replace_own_protected_zones,
    save_health_questionnaire,
    update_profile,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/students", tags=["students"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def profile_response(profile: StudentProfile, db: Session) -> StudentProfileResponse:
    response = StudentProfileResponse.model_validate(profile)
    response.health_questionnaire_completed = is_questionnaire_completed(db, profile)
    return response


def handle_error(error: StudentProfileError) -> None:
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
