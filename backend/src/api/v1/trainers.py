from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.user import User
from backend.src.schemas.trainer import TrainerProfileResponse, TrainerProfileUpdate
from backend.src.services.trainer_service import (
    TrainerProfileError,
    get_or_create_profile,
    get_published_profile,
    update_profile,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/trainers", tags=["trainers"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def profile_response(profile: TrainerProfile) -> TrainerProfileResponse:
    response = TrainerProfileResponse.model_validate(profile)
    return response.model_copy(update={"available_slots": profile.max_students})


def handle_error(error: TrainerProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/me/profile", response_model=TrainerProfileResponse)
def own_profile(user: CurrentUser, db: DbDep) -> TrainerProfileResponse:
    try:
        return profile_response(get_or_create_profile(db, user))
    except TrainerProfileError as error:
        handle_error(error)


@router.put("/me/profile", response_model=TrainerProfileResponse)
def save_own_profile(payload: TrainerProfileUpdate, user: CurrentUser, db: DbDep) -> TrainerProfileResponse:
    try:
        return profile_response(update_profile(db, user, payload))
    except TrainerProfileError as error:
        handle_error(error)


@router.get("/{trainer_id}/profile", response_model=TrainerProfileResponse)
def published_profile(trainer_id: str, _: CurrentUser, db: DbDep) -> TrainerProfileResponse:
    try:
        return profile_response(get_published_profile(db, trainer_id))
    except TrainerProfileError as error:
        handle_error(error)
