from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.routine_template import (
    RoutineAssignmentResponse,
    RoutineAssignmentStudentResponse,
    RoutineAssignmentUpdate,
    RoutineTemplateInput,
    RoutineTemplateResponse,
)
from backend.src.services.routine_template_service import (
    RoutineTemplateError,
    assign_routine_to_student,
    create_template,
    get_assigned_student_template,
    get_own_template,
    get_student_template,
    list_own_templates,
    list_routine_assignments,
    list_student_templates,
    update_template,
)
from backend.src.services.student_routine_service import (
    on_reassign,
    student_assigned_view,
)
from backend.src.services.student_service import StudentProfileError
from backend.src.services.trainer_service import TrainerProfileError

router = APIRouter(prefix=f"{API_V1_PREFIX}/routine-templates", tags=["routine-templates"])
student_router = APIRouter(prefix=f"{API_V1_PREFIX}/students/me/routine-templates", tags=["routine-templates"])
CurrentUser = Annotated[User, Depends(get_current_user)]
ServiceErrors = (RoutineTemplateError, TrainerProfileError, StudentProfileError)


def handle_error(error: RoutineTemplateError | TrainerProfileError | StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("", response_model=list[RoutineTemplateResponse])
def list_templates(user: CurrentUser, db: DbDep) -> list[RoutineTemplateResponse]:
    try:
        return [RoutineTemplateResponse.model_validate(item) for item in list_own_templates(db, user)]
    except ServiceErrors as error:
        handle_error(error)


@router.post("", response_model=RoutineTemplateResponse, status_code=status.HTTP_201_CREATED)
def add_template(payload: RoutineTemplateInput, user: CurrentUser, db: DbDep) -> RoutineTemplateResponse:
    try:
        return RoutineTemplateResponse.model_validate(create_template(db, user, payload))
    except ServiceErrors as error:
        handle_error(error)


@router.get("/assignments", response_model=list[RoutineAssignmentStudentResponse])
def active_student_routine_assignments(user: CurrentUser, db: DbDep) -> list[RoutineAssignmentStudentResponse]:
    try:
        return [RoutineAssignmentStudentResponse(**item) for item in list_routine_assignments(db, user)]
    except ServiceErrors as error:
        handle_error(error)


@router.put("/assignments/{relationship_id}", response_model=RoutineAssignmentResponse)
def save_student_routine_assignment(
    relationship_id: str,
    payload: RoutineAssignmentUpdate,
    user: CurrentUser,
    db: DbDep,
) -> RoutineAssignmentResponse:
    try:
        assignment = assign_routine_to_student(db, user, relationship_id, payload.routine_template_id)
        on_reassign(db, relationship_id, payload.routine_template_id)
        return RoutineAssignmentResponse(**assignment)
    except ServiceErrors as error:
        handle_error(error)


@router.get("/{template_id}", response_model=RoutineTemplateResponse)
def template_detail(template_id: str, user: CurrentUser, db: DbDep) -> RoutineTemplateResponse:
    try:
        return RoutineTemplateResponse.model_validate(get_own_template(db, user, template_id))
    except ServiceErrors as error:
        handle_error(error)


@router.put("/{template_id}", response_model=RoutineTemplateResponse)
def edit_template(
    template_id: str, payload: RoutineTemplateInput, user: CurrentUser, db: DbDep
) -> RoutineTemplateResponse:
    try:
        return RoutineTemplateResponse.model_validate(update_template(db, user, template_id, payload))
    except ServiceErrors as error:
        handle_error(error)


@student_router.get("", response_model=list[RoutineTemplateResponse])
def list_available_templates(user: CurrentUser, db: DbDep) -> list[RoutineTemplateResponse]:
    try:
        return [RoutineTemplateResponse.model_validate(item) for item in list_student_templates(db, user)]
    except ServiceErrors as error:
        handle_error(error)


@student_router.get("/assigned", response_model=RoutineTemplateResponse | None)
def assigned_routine(user: CurrentUser, db: DbDep) -> RoutineTemplateResponse | None:
    try:
        own_copy = student_assigned_view(db, user)
        if own_copy is not None:
            return RoutineTemplateResponse.model_validate(own_copy)
        template = get_assigned_student_template(db, user)
        return RoutineTemplateResponse.model_validate(template) if template else None
    except ServiceErrors as error:
        handle_error(error)


@student_router.get("/{template_id}", response_model=RoutineTemplateResponse)
def available_template_detail(template_id: str, user: CurrentUser, db: DbDep) -> RoutineTemplateResponse:
    try:
        return RoutineTemplateResponse.model_validate(get_student_template(db, user, template_id))
    except ServiceErrors as error:
        handle_error(error)
