from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.exercise import ExerciseInput, ExerciseResponse
from backend.src.services.exercise_service import (
    ExerciseError,
    create_exercise,
    delete_exercise,
    get_own_exercise,
    list_own_exercises,
    update_exercise,
)
from backend.src.services.trainer_service import TrainerProfileError

router = APIRouter(prefix=f"{API_V1_PREFIX}/exercises", tags=["exercises"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def handle_error(error: ExerciseError | TrainerProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("", response_model=list[ExerciseResponse])
def list_exercises(
    user: CurrentUser, db: DbDep, muscle_group: Annotated[str | None, Query()] = None
) -> list[ExerciseResponse]:
    try:
        return [ExerciseResponse.model_validate(item) for item in list_own_exercises(db, user, muscle_group)]
    except (ExerciseError, TrainerProfileError) as error:
        handle_error(error)


@router.post("", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
def add_exercise(payload: ExerciseInput, user: CurrentUser, db: DbDep) -> ExerciseResponse:
    try:
        return ExerciseResponse.model_validate(create_exercise(db, user, payload))
    except (ExerciseError, TrainerProfileError) as error:
        handle_error(error)


@router.get("/{exercise_id}", response_model=ExerciseResponse)
def exercise_detail(exercise_id: str, user: CurrentUser, db: DbDep) -> ExerciseResponse:
    try:
        return ExerciseResponse.model_validate(get_own_exercise(db, user, exercise_id))
    except (ExerciseError, TrainerProfileError) as error:
        handle_error(error)


@router.put("/{exercise_id}", response_model=ExerciseResponse)
def edit_exercise(exercise_id: str, payload: ExerciseInput, user: CurrentUser, db: DbDep) -> ExerciseResponse:
    try:
        return ExerciseResponse.model_validate(update_exercise(db, user, exercise_id, payload))
    except (ExerciseError, TrainerProfileError) as error:
        handle_error(error)


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_exercise(exercise_id: str, user: CurrentUser, db: DbDep) -> None:
    try:
        delete_exercise(db, user, exercise_id)
    except (ExerciseError, TrainerProfileError) as error:
        handle_error(error)
