from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.models.user import User
from backend.src.schemas.discovery import (
    ActivePlanResponse,
    NotificationItem,
    NotificationListResponse,
    PaginatedTrainers,
    TrainerPublicDetail,
    TrainerSearchFilters,
    TrainingRelationshipResponse,
    TrainingRequestAcceptPayload,
    TrainingRequestCreate,
    TrainingRequestDetailResponse,
    TrainingRequestRejectPayload,
    TrainingRequestResponse,
    TrainingRequestStatus,
)
from backend.src.services.discovery_service import (
    DiscoveryError,
    accept_training_request,
    create_training_request,
    get_public_detail,
    get_student_active_plan,
    get_student_active_plans,
    get_trainer_request_detail,
    list_student_requests,
    list_trainer_requests,
    reject_training_request,
    search_trainers,
)
from backend.src.services.notification_service import (
    NotificationError,
    list_user_notifications,
    mark_notification_as_read,
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
    max_price: float | None = Query(default=None, ge=0),
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


@router.get("/matchmaking/requests", response_model=list[TrainingRequestResponse])
def trainer_requests_inbox(
    user: CurrentUser,
    db: DbDep,
    status_filter: Annotated[TrainingRequestStatus | None, Query(alias="status")] = None,
) -> list[TrainingRequestResponse]:
    try:
        return list_trainer_requests(db, user, status_filter=status_filter)
    except DiscoveryError as error:
        handle_error(error)


@router.get("/matchmaking/requests/mine", response_model=list[TrainingRequestResponse])
def my_training_requests(user: CurrentUser, db: DbDep) -> list[TrainingRequestResponse]:
    try:
        return list_student_requests(db, user)
    except DiscoveryError as error:
        handle_error(error)


@router.get("/matchmaking/requests/{request_id}", response_model=TrainingRequestDetailResponse)
def trainer_request_detail(
    request_id: str, user: CurrentUser, db: DbDep
) -> TrainingRequestDetailResponse:
    try:
        return get_trainer_request_detail(db, user, request_id)
    except DiscoveryError as error:
        handle_error(error)


@router.post(
    "/matchmaking/requests/{request_id}/accept",
    response_model=TrainingRelationshipResponse,
    status_code=status.HTTP_200_OK,
)
def accept_request_endpoint(
    request_id: str,
    user: CurrentUser,
    db: DbDep,
    payload: Annotated[TrainingRequestAcceptPayload | None, Body()] = None,
) -> TrainingRelationshipResponse:
    try:
        return accept_training_request(db, user, request_id, payload)
    except DiscoveryError as error:
        handle_error(error)


@router.post(
    "/matchmaking/requests/{request_id}/reject",
    response_model=TrainingRequestResponse,
    status_code=status.HTTP_200_OK,
)
def reject_request_endpoint(
    request_id: str,
    user: CurrentUser,
    db: DbDep,
    payload: Annotated[TrainingRequestRejectPayload | None, Body()] = None,
) -> TrainingRequestResponse:
    try:
        return reject_training_request(db, user, request_id, payload)
    except DiscoveryError as error:
        handle_error(error)


@router.get("/students/me/active-plans", response_model=list[ActivePlanResponse])
def student_active_plans(user: CurrentUser, db: DbDep) -> list[ActivePlanResponse]:
    try:
        return get_student_active_plans(db, user)
    except DiscoveryError as error:
        handle_error(error)


@router.get("/students/me/active-plan", response_model=ActivePlanResponse)
def student_active_plan(user: CurrentUser, db: DbDep) -> ActivePlanResponse:
    try:
        return get_student_active_plan(db, user)
    except DiscoveryError as error:
        handle_error(error)


@router.get("/students/me/notifications", response_model=NotificationListResponse)
def student_notifications(
    user: CurrentUser,
    db: DbDep,
    is_read: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    try:
        return list_user_notifications(
            db, user, is_read=is_read, limit=limit, offset=offset, expected_role=STUDENT_ROLE
        )
    except NotificationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch("/students/me/notifications/{notification_id}/read", response_model=NotificationItem)
def mark_notification_read(
    notification_id: str,
    user: CurrentUser,
    db: DbDep,
) -> NotificationItem:
    try:
        return mark_notification_as_read(db, user, notification_id, expected_role=STUDENT_ROLE)
    except NotificationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/trainers/me/notifications", response_model=NotificationListResponse)
def trainer_notifications(
    user: CurrentUser,
    db: DbDep,
    is_read: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    try:
        return list_user_notifications(
            db, user, is_read=is_read, limit=limit, offset=offset, expected_role=TRAINER_ROLE
        )
    except NotificationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch("/trainers/me/notifications/{notification_id}/read", response_model=NotificationItem)
def mark_trainer_notification_read(
    notification_id: str,
    user: CurrentUser,
    db: DbDep,
) -> NotificationItem:
    try:
        return mark_notification_as_read(db, user, notification_id, expected_role=TRAINER_ROLE)
    except NotificationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
