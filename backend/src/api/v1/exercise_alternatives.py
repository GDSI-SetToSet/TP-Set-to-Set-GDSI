from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.exercise_alternative import (
    AlternativesResponse,
    ReplacementInput,
    ReplacementResponse,
)
from backend.src.services import exercise_alternative_service as service
from backend.src.services.exercise_service import ExerciseError
from backend.src.services.student_service import StudentProfileError

router = APIRouter(prefix=f"{API_V1_PREFIX}/students/me", tags=["exercise-alternatives"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def fail(error: ExerciseError | StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if getattr(error, "errors", None) is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/exercises/{exercise_id}/alternatives", response_model=AlternativesResponse)
def alternatives(exercise_id: str, user: CurrentUser, db: DbDep) -> dict:
    try:
        return service.list_alternatives(db, user, exercise_id)
    except (ExerciseError, StudentProfileError) as error:
        fail(error)


@router.put("/exercise-replacements", response_model=ReplacementResponse)
def replace(payload: ReplacementInput, user: CurrentUser, db: DbDep) -> ReplacementResponse:
    try:
        log = service.record_replacement(db, user, payload)
        return ReplacementResponse(
            original_exercise_id=log.original_exercise_id, replacement_exercise_id=log.replacement_exercise_id
        )
    except (ExerciseError, StudentProfileError) as error:
        fail(error)
