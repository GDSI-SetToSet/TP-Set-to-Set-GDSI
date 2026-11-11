from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.safe_variant import (
    SafeVariantInput,
    SafeVariantResolution,
    SafeVariantResponse,
    SafeVariantZones,
)
from backend.src.services import safe_variant_service as service
from backend.src.services.exercise_service import ExerciseError
from backend.src.services.student_service import StudentProfileError
from backend.src.services.trainer_service import TrainerProfileError

router = APIRouter(prefix=f"{API_V1_PREFIX}/exercises/{{exercise_id}}/safe-variants", tags=["safe-variants"])
student_router = APIRouter(
    prefix=f"{API_V1_PREFIX}/students/me/exercises/{{exercise_id}}/safe-variant", tags=["safe-variants"]
)
CurrentUser = Annotated[User, Depends(get_current_user)]
ServiceErrors = (ExerciseError, TrainerProfileError, StudentProfileError)


def fail(error: ExerciseError | TrainerProfileError | StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if getattr(error, "errors", None) is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("", response_model=list[SafeVariantResponse])
def list_variants(exercise_id: str, user: CurrentUser, db: DbDep) -> list[dict]:
    try:
        return service.list_variants(db, user, exercise_id)
    except ServiceErrors as error:
        fail(error)


@router.post("", response_model=SafeVariantResponse, status_code=status.HTTP_201_CREATED)
def add_variant(exercise_id: str, payload: SafeVariantInput, user: CurrentUser, db: DbDep) -> dict:
    try:
        link = service.create_variant(db, user, exercise_id, payload)
        return next(v for v in service.list_variants(db, user, exercise_id) if v["id"] == link.id)
    except ServiceErrors as error:
        fail(error)


@router.put("/{variant_id}", response_model=SafeVariantResponse)
def edit_variant(exercise_id: str, variant_id: str, payload: SafeVariantZones, user: CurrentUser, db: DbDep) -> dict:
    try:
        service.update_variant(db, user, exercise_id, variant_id, payload)
        return next(v for v in service.list_variants(db, user, exercise_id) if v["id"] == variant_id)
    except ServiceErrors as error:
        fail(error)


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_variant(exercise_id: str, variant_id: str, user: CurrentUser, db: DbDep) -> Response:
    try:
        service.delete_variant(db, user, exercise_id, variant_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ServiceErrors as error:
        fail(error)


@student_router.get("", response_model=SafeVariantResolution)
def resolve(exercise_id: str, user: CurrentUser, db: DbDep) -> dict:
    try:
        return service.resolve_for_student(db, user, exercise_id)
    except ServiceErrors as error:
        fail(error)
