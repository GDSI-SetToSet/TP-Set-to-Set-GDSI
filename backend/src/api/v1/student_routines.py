from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.routine_template import RoutineTemplateResponse
from backend.src.schemas.student_routine import (
    DraftSavedResponse,
    RoutineDraftInput,
    StudentRoutineResponse,
)
from backend.src.services import student_routine_service as service
from backend.src.services.routine_template_service import RoutineTemplateError
from backend.src.services.student_service import StudentProfileError
from backend.src.services.trainer_service import TrainerProfileError

router = APIRouter(prefix=f"{API_V1_PREFIX}/trainers/me/students/{{student_id}}/routine", tags=["student-routines"])
CurrentUser = Annotated[User, Depends(get_current_user)]
ServiceErrors = (RoutineTemplateError, TrainerProfileError, StudentProfileError)


def fail(error: RoutineTemplateError | TrainerProfileError | StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


def view(db, routine) -> StudentRoutineResponse:
    draft = routine.draft
    return StudentRoutineResponse(
        routine=RoutineTemplateResponse.model_validate(service.render(db, routine)),
        draft=RoutineTemplateResponse.model_validate(service.render(db, routine, draft)) if draft else None,
        draft_version=routine.draft_version,
        desired_weekly_volume=draft["desired_weekly_volume"] if draft else routine.desired_weekly_volume,
        status=routine.status,
    )


@router.get("", response_model=StudentRoutineResponse)
def get_routine(student_id: str, user: CurrentUser, db: DbDep) -> StudentRoutineResponse:
    try:
        return view(db, service.get_routine(db, user, student_id))
    except ServiceErrors as error:
        fail(error)


@router.put("/draft", response_model=DraftSavedResponse)
def put_draft(student_id: str, payload: RoutineDraftInput, user: CurrentUser, db: DbDep) -> DraftSavedResponse:
    try:
        return DraftSavedResponse(draft_version=service.save_draft(db, user, student_id, payload).draft_version)
    except ServiceErrors as error:
        fail(error)


@router.delete("/draft", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(student_id: str, user: CurrentUser, db: DbDep) -> Response:
    try:
        service.discard_draft(db, user, student_id)
    except ServiceErrors as error:
        fail(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/draft/confirm", response_model=StudentRoutineResponse)
def confirm(student_id: str, user: CurrentUser, db: DbDep) -> StudentRoutineResponse:
    try:
        return view(db, service.confirm_draft(db, user, student_id))
    except ServiceErrors as error:
        fail(error)
