from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.student_profile import StudentProfile
from backend.src.models.user import User
from backend.src.schemas.student import (
    StudentGoalsResponse,
    StudentProfileResponse,
    StudentProfileUpdate,
)
from backend.src.services.student_service import (
    StudentProfileError,
    get_goals_for_viewer,
    get_or_create_profile,
    update_profile,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/students", tags=["students"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def profile_response(profile: StudentProfile) -> StudentProfileResponse:
    return StudentProfileResponse.model_validate(profile)


def handle_error(error: StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/me/profile", response_model=StudentProfileResponse)
def own_profile(user: CurrentUser, db: DbDep) -> StudentProfileResponse:
    try:
        return profile_response(get_or_create_profile(db, user))
    except StudentProfileError as error:
        handle_error(error)


@router.put("/me/profile", response_model=StudentProfileResponse)
def save_own_profile(payload: StudentProfileUpdate, user: CurrentUser, db: DbDep) -> StudentProfileResponse:
    try:
        return profile_response(update_profile(db, user, payload))
    except StudentProfileError as error:
        handle_error(error)


@router.get("/{student_id}/goals", response_model=StudentGoalsResponse)
def student_goals(student_id: str, user: CurrentUser, db: DbDep) -> StudentGoalsResponse:
    try:
        return StudentGoalsResponse.model_validate(get_goals_for_viewer(db, user, student_id))
    except StudentProfileError as error:
        handle_error(error)
