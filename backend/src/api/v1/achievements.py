"""Rutas de logros y felicitaciones (US-67)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.achievement import (
    AchievementItem,
    AchievementsOverview,
    CongratulationCreate,
)
from backend.src.services.achievement_service import (
    AchievementError,
    congratulate,
    get_student_achievements,
    get_trainer_student_achievements,
    mark_celebrated,
    mark_congratulation_seen,
)
from backend.src.services.trainer_student_service import TrainerStudentError

router = APIRouter(prefix=API_V1_PREFIX, tags=["achievements"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def handle_error(error: AchievementError | TrainerStudentError) -> None:
    detail: str | dict[str, object] = error.detail
    if getattr(error, "errors", None) is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/students/me/achievements", response_model=AchievementsOverview)
def own_achievements(user: CurrentUser, db: DbDep) -> AchievementsOverview:
    """US-67 escenarios 1 y 3: logros desbloqueados con su fecha y avance de los que faltan."""
    try:
        return get_student_achievements(db, user)
    except AchievementError as error:
        handle_error(error)


@router.post("/students/me/achievements/{achievement_id}/celebrated", status_code=status.HTTP_204_NO_CONTENT)
def achievement_celebrated(achievement_id: str, user: CurrentUser, db: DbDep) -> Response:
    """US-67 escenario 2: el alumno cerró la celebración."""
    try:
        mark_celebrated(db, user, achievement_id)
    except AchievementError as error:
        handle_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/students/me/achievements/{achievement_id}/congratulation/seen", status_code=status.HTTP_204_NO_CONTENT)
def congratulation_seen(achievement_id: str, user: CurrentUser, db: DbDep) -> Response:
    """US-67 escenario 4: la felicitación se muestra una sola vez."""
    try:
        mark_congratulation_seen(db, user, achievement_id)
    except AchievementError as error:
        handle_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/trainers/me/students/{student_id}/achievements", response_model=AchievementsOverview)
def trainer_student_achievements(student_id: str, user: CurrentUser, db: DbDep) -> AchievementsOverview:
    """US-67 escenario 4: logros del alumno activo."""
    try:
        return get_trainer_student_achievements(db, user, student_id)
    except (AchievementError, TrainerStudentError) as error:
        handle_error(error)


@router.post(
    "/trainers/me/achievements/{achievement_id}/congratulation",
    response_model=AchievementItem,
    status_code=status.HTTP_201_CREATED,
)
def trainer_congratulate(
    achievement_id: str, payload: CongratulationCreate, user: CurrentUser, db: DbDep
) -> AchievementItem:
    """US-67 escenario 4: felicitación del entrenador por un logro de su alumno."""
    try:
        return congratulate(db, user, achievement_id, payload.message)
    except (AchievementError, TrainerStudentError) as error:
        handle_error(error)
