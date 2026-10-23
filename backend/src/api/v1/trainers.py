from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.user import User
from backend.src.schemas.trainer import (
    TrainerProfileResponse,
    TrainerProfileUpdate,
    TrainingPlanCreate,
    TrainingPlanResponse,
    TrainingPlanUpdate,
)
from backend.src.services.trainer_service import (
    TrainerProfileError,
    archive_plan,
    create_plan,
    get_or_create_profile,
    get_published_profile,
    list_own_plans,
    list_published_plans,
    update_plan,
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


@router.get("/me/plans", response_model=list[TrainingPlanResponse])
def own_plans(user: CurrentUser, db: DbDep) -> list[TrainingPlanResponse]:
    try:
        return [TrainingPlanResponse.model_validate(plan) for plan in list_own_plans(db, user)]
    except TrainerProfileError as error:
        handle_error(error)


@router.post("/me/plans", response_model=TrainingPlanResponse, status_code=status.HTTP_201_CREATED)
def publish_plan(payload: TrainingPlanCreate, user: CurrentUser, db: DbDep) -> TrainingPlanResponse:
    try:
        return TrainingPlanResponse.model_validate(create_plan(db, user, payload))
    except TrainerProfileError as error:
        handle_error(error)


@router.put("/me/plans/{plan_id}", response_model=TrainingPlanResponse)
def edit_plan(plan_id: str, payload: TrainingPlanUpdate, user: CurrentUser, db: DbDep) -> TrainingPlanResponse:
    try:
        return TrainingPlanResponse.model_validate(update_plan(db, user, plan_id, payload))
    except TrainerProfileError as error:
        handle_error(error)


@router.post("/me/plans/{plan_id}/archive", response_model=TrainingPlanResponse)
def archive_own_plan(plan_id: str, user: CurrentUser, db: DbDep) -> TrainingPlanResponse:
    try:
        return TrainingPlanResponse.model_validate(archive_plan(db, user, plan_id))
    except TrainerProfileError as error:
        handle_error(error)


@router.get("/{trainer_id}/plans", response_model=list[TrainingPlanResponse])
def published_plans(trainer_id: str, _: CurrentUser, db: DbDep) -> list[TrainingPlanResponse]:
    try:
        return [TrainingPlanResponse.model_validate(plan) for plan in list_published_plans(db, trainer_id)]
    except TrainerProfileError as error:
        handle_error(error)
