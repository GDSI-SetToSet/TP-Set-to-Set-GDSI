from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.core.rate_limiter import SimpleRateLimiter
from backend.src.models.user import User
from backend.src.schemas.assigned_routine import (
    ActiveStudentResponse,
    AssignedRoutineResponse,
    AssignedRoutineUpdateInput,
    GenerateAIRoutineInput,
    TrainerAIRoutineResponse,
)
from backend.src.services.assigned_routine_service import (
    AssignedRoutineError,
    approve_assigned_routine,
    delete_assigned_routine,
    generate_ai_routine_proposal,
    get_active_routine_for_student,
    get_assigned_routine_detail,
    list_active_students_for_trainer,
    list_trainer_ai_routines,
    update_assigned_routine,
)
from backend.src.services.student_service import StudentProfileError
from backend.src.services.trainer_service import TrainerProfileError

router = APIRouter(prefix=API_V1_PREFIX, tags=["assigned-routines"])
ai_generate_limiter = SimpleRateLimiter(
    max_requests=10,
    window_seconds=60,
    detail="Se superó el límite de generación de rutinas por minuto. Intentá nuevamente más tarde.",
)
CurrentUser = Annotated[User, Depends(get_current_user)]
ServiceErrors = (AssignedRoutineError, TrainerProfileError, StudentProfileError)


def handle_error(error: AssignedRoutineError | TrainerProfileError | StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    errors = getattr(error, "errors", None)
    if errors is not None:
        detail = {"detail": error.detail, "errors": errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/trainers/me/active-students", response_model=list[ActiveStudentResponse])
def get_trainer_active_students(user: CurrentUser, db: DbDep) -> list[ActiveStudentResponse]:
    try:
        return list_active_students_for_trainer(db, user)
    except ServiceErrors as error:
        handle_error(error)


@router.post(
    "/routines/generate-ai",
    response_model=AssignedRoutineResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_ai_routine(
    payload: GenerateAIRoutineInput, user: CurrentUser, db: DbDep
) -> AssignedRoutineResponse:
    ai_generate_limiter.check(user.id)
    try:
        routine = generate_ai_routine_proposal(db, user, payload)
        return AssignedRoutineResponse.model_validate(routine)
    except ServiceErrors as error:
        handle_error(error)


@router.get("/routines/assigned", response_model=list[TrainerAIRoutineResponse])
def get_trainer_ai_routines(user: CurrentUser, db: DbDep) -> list[TrainerAIRoutineResponse]:
    try:
        return list_trainer_ai_routines(db, user)
    except ServiceErrors as error:
        handle_error(error)


@router.delete("/routines/assigned/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assigned_routine(routine_id: str, user: CurrentUser, db: DbDep) -> None:
    try:
        delete_assigned_routine(db, user, routine_id)
    except ServiceErrors as error:
        handle_error(error)


@router.get("/routines/assigned/{routine_id}", response_model=AssignedRoutineResponse)
def get_assigned_routine(routine_id: str, user: CurrentUser, db: DbDep) -> AssignedRoutineResponse:
    try:
        routine = get_assigned_routine_detail(db, user, routine_id)
        return AssignedRoutineResponse.model_validate(routine)
    except ServiceErrors as error:
        handle_error(error)


@router.put("/routines/assigned/{routine_id}", response_model=AssignedRoutineResponse)
def edit_assigned_routine(
    routine_id: str,
    payload: AssignedRoutineUpdateInput,
    user: CurrentUser,
    db: DbDep,
) -> AssignedRoutineResponse:
    try:
        routine = update_assigned_routine(db, user, routine_id, payload)
        return AssignedRoutineResponse.model_validate(routine)
    except ServiceErrors as error:
        handle_error(error)


@router.post("/routines/assigned/{routine_id}/approve", response_model=AssignedRoutineResponse)
def approve_routine(routine_id: str, user: CurrentUser, db: DbDep) -> AssignedRoutineResponse:
    try:
        routine = approve_assigned_routine(db, user, routine_id)
        return AssignedRoutineResponse.model_validate(routine)
    except ServiceErrors as error:
        handle_error(error)


@router.get("/students/me/assigned-routine", response_model=AssignedRoutineResponse | None)
def get_student_assigned_routine(user: CurrentUser, db: DbDep) -> AssignedRoutineResponse | None:
    try:
        routine = get_active_routine_for_student(db, user)
        return AssignedRoutineResponse.model_validate(routine) if routine else None
    except ServiceErrors as error:
        handle_error(error)
