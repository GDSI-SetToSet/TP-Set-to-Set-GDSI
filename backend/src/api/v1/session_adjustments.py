"""US-26: ajuste de la próxima sesión del alumno a partir de su sesión finalizada."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.session_adjustment import (
    AdjustmentInput,
    AdjustmentView,
    SessionAdjustmentContext,
    StudentAdjustmentNotice,
)
from backend.src.services import session_adjustment_service as service
from backend.src.services.routine_template_service import RoutineTemplateError
from backend.src.services.student_service import StudentProfileError
from backend.src.services.trainer_service import TrainerProfileError

router = APIRouter(prefix=f"{API_V1_PREFIX}/trainers/me/sessions/{{session_id}}/adjustment", tags=["session-adjustments"])
student_router = APIRouter(prefix=f"{API_V1_PREFIX}/students/me/routine-adjustments", tags=["session-adjustments"])
CurrentUser = Annotated[User, Depends(get_current_user)]
ServiceErrors = (RoutineTemplateError, TrainerProfileError, StudentProfileError)


def fail(error: RoutineTemplateError | TrainerProfileError | StudentProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("", response_model=SessionAdjustmentContext)
def adjustment_context(session_id: str, user: CurrentUser, db: DbDep) -> SessionAdjustmentContext:
    """Reportes de la sesión finalizada y el día de rutina a ajustar."""
    try:
        return service.get_adjustment_context(db, user, session_id)
    except ServiceErrors as error:
        fail(error)


@router.put("", response_model=AdjustmentView)
def save_adjustment(session_id: str, payload: AdjustmentInput, user: CurrentUser, db: DbDep) -> AdjustmentView:
    try:
        return service.save_adjustment(db, user, session_id, payload)
    except ServiceErrors as error:
        fail(error)


@student_router.get("", response_model=list[StudentAdjustmentNotice])
def student_adjustments(user: CurrentUser, db: DbDep) -> list[StudentAdjustmentNotice]:
    """Días con ejercicios "Ajustado por tu entrenador" que el alumno todavía no entrenó."""
    try:
        return service.list_student_adjustments(db, user)
    except ServiceErrors as error:
        fail(error)
