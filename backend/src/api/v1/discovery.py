from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.discovery import (
    PaginatedTrainers,
    TrainerPublicDetail,
    TrainerSearchFilters,
    TrainingRequestCreate,
    TrainingRequestResponse,
)
from backend.src.services.discovery_service import (
    DiscoveryError,
    create_training_request,
    get_public_detail,
    list_student_requests,
    search_trainers,
)
from backend.src.services.trainer_service import TrainerProfileError

router = APIRouter(prefix=API_V1_PREFIX, tags=["discovery"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def handle_error(error: DiscoveryError | TrainerProfileError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/trainers/search", response_model=PaginatedTrainers)
def trainer_search(
    _: CurrentUser,
    db: DbDep,
    specialty: str | None = Query(default=None),
    max_price: float | None = Query(default=None),
    only_available: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> PaginatedTrainers:
    filters = TrainerSearchFilters(
        specialty=specialty,
        max_price=max_price,
        only_available=only_available,
        page=page,
        page_size=page_size,
    )
    return search_trainers(db, filters)


@router.get("/trainers/{trainer_id}/public", response_model=TrainerPublicDetail)
def trainer_public_detail(trainer_id: str, _: CurrentUser, db: DbDep) -> TrainerPublicDetail:
    try:
        return get_public_detail(db, trainer_id)
    except TrainerProfileError as error:
        handle_error(error)


@router.post(
    "/matchmaking/requests",
    response_model=TrainingRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_training_request(
    payload: TrainingRequestCreate, user: CurrentUser, db: DbDep
) -> TrainingRequestResponse:
    try:
        return create_training_request(db, user, payload)
    except DiscoveryError as error:
        handle_error(error)


@router.get("/matchmaking/requests/mine", response_model=list[TrainingRequestResponse])
def my_training_requests(user: CurrentUser, db: DbDep) -> list[TrainingRequestResponse]:
    try:
        return list_student_requests(db, user)
    except DiscoveryError as error:
        handle_error(error)
