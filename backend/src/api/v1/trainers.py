from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.user import User
from backend.src.schemas.informal_payment import (
    PaymentCreate,
    PaymentHistory,
    PaymentMutationResult,
    PaymentVoidRequest,
    SubscriptionStatus,
    SubscriptionSummary,
)
from backend.src.schemas.safety_alert import (
    SafetyAlertReviewRequest,
    SafetyAlertStatus,
    SafetyAlertView,
)
from backend.src.schemas.trainer import (
    TrainerProfileResponse,
    TrainerProfileUpdate,
    TrainerQuotaResponse,
    TrainerQuotaUpdate,
    TrainingPlanCreate,
    TrainingPlanResponse,
    TrainingPlanUpdate,
)
from backend.src.schemas.trainer_student import (
    AbandonmentRiskItem,
    DailyRoutineItem,
    SessionComparison,
    StudentTerminationRequest,
    StudentTerminationResult,
    TrainerStudentDetail,
    TrainerStudentListItem,
    TrainingEvolution,
)
from backend.src.services.abandonment_risk_service import list_abandonment_risk
from backend.src.services.daily_routine_tracking_service import list_daily_routines
from backend.src.services.informal_payment_service import (
    PaymentError,
    get_payment_history,
    list_subscriptions,
    register_payment,
    void_payment,
)
from backend.src.services.safety_alert_service import (
    SafetyAlertError,
    list_trainer_safety_alerts,
    list_trainer_student_safety_alerts,
    review_safety_alert,
)
from backend.src.services.session_comparison_service import compare_session
from backend.src.services.student_termination_service import terminate_student
from backend.src.services.trainer_service import (
    TrainerProfileError,
    archive_plan,
    create_plan,
    get_or_create_profile,
    get_published_profile,
    list_own_plans,
    list_published_plans,
    quota_summary,
    update_plan,
    update_profile,
    update_quota,
)
from backend.src.services.trainer_student_service import (
    TrainerStudentError,
    get_trainer_student_detail,
    list_trainer_students,
)
from backend.src.services.training_evolution_service import get_training_evolution

router = APIRouter(prefix=f"{API_V1_PREFIX}/trainers", tags=["trainers"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def profile_response(db: Session, profile: TrainerProfile) -> TrainerProfileResponse:
    quota = quota_summary(db, profile)
    response = TrainerProfileResponse.model_validate(profile)
    return response.model_copy(
        update={
            "active_students_count": quota["active_students"],
            "available_slots": quota["available_slots"],
            "has_available_quota": quota["has_available_quota"],
        }
    )


def handle_error(error: TrainerProfileError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


def handle_student_error(error: TrainerStudentError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def handle_safety_alert_error(error: SafetyAlertError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/me/students", response_model=list[TrainerStudentListItem])
def own_active_students(user: CurrentUser, db: DbDep) -> list[TrainerStudentListItem]:
    try:
        return list_trainer_students(db, user)
    except TrainerStudentError as error:
        handle_student_error(error)


@router.get("/me/daily-routines", response_model=list[DailyRoutineItem])
def own_students_daily_routines(
    user: CurrentUser,
    db: DbDep,
    day: Annotated[date | None, Query(alias="date")] = None,
    utc_offset_minutes: Annotated[int, Query(ge=-840, le=840)] = 0,
) -> list[DailyRoutineItem]:
    """US-22: estado y registro de la rutina del día de cada alumno activo."""
    try:
        return list_daily_routines(db, user, day or date.today(), utc_offset_minutes)
    except TrainerStudentError as error:
        handle_student_error(error)


LocalDate = Annotated[date | None, Query(alias="date", description="Fecha local del entrenador (hoy).")]


@router.get("/me/subscriptions", response_model=list[SubscriptionSummary])
def own_students_subscriptions(
    user: CurrentUser,
    db: DbDep,
    day: LocalDate = None,
    subscription_status: Annotated[SubscriptionStatus | None, Query(alias="status")] = None,
) -> list[SubscriptionSummary]:
    """US-34: estado de la suscripción de cada alumno activo (vencidas primero)."""
    try:
        return list_subscriptions(db, user, day or date.today(), subscription_status)
    except PaymentError as error:
        handle_error(error)


@router.get("/me/students/{student_id}/payments", response_model=PaymentHistory)
def own_student_payment_history(
    student_id: str, user: CurrentUser, db: DbDep, day: LocalDate = None
) -> PaymentHistory:
    """US-34: suscripción e historial completo de pagos del alumno, incluidos los anulados."""
    try:
        return get_payment_history(db, user, student_id, day or date.today())
    except PaymentError as error:
        handle_error(error)


@router.post(
    "/me/students/{student_id}/payments",
    response_model=PaymentMutationResult,
    status_code=status.HTTP_201_CREATED,
)
def own_student_register_payment(
    student_id: str, payload: PaymentCreate, user: CurrentUser, db: DbDep, day: LocalDate = None
) -> PaymentMutationResult:
    """US-34: registra un pago recibido por fuera de la app y extiende el vencimiento."""
    try:
        return register_payment(db, user, student_id, payload, day or date.today())
    except PaymentError as error:
        handle_error(error)


@router.post("/me/payments/{payment_id}/void", response_model=PaymentMutationResult)
def own_student_void_payment(
    payment_id: str, payload: PaymentVoidRequest, user: CurrentUser, db: DbDep, day: LocalDate = None
) -> PaymentMutationResult:
    """US-34: anula un pago con motivo obligatorio; los pagos nunca se eliminan."""
    try:
        return void_payment(db, user, payment_id, payload.reason, day or date.today())
    except PaymentError as error:
        handle_error(error)


@router.get("/me/sessions/{session_id}/comparison", response_model=SessionComparison)
def own_student_session_comparison(session_id: str, user: CurrentUser, db: DbDep) -> SessionComparison:
    """US-24: sesión finalizada vs lo planificado y vs la sesión previa del mismo día de rutina."""
    try:
        return compare_session(db, user, session_id)
    except TrainerStudentError as error:
        handle_student_error(error)


@router.get("/me/abandonment-risk", response_model=list[AbandonmentRiskItem])
def own_students_abandonment_risk(user: CurrentUser, db: DbDep) -> list[AbandonmentRiskItem]:
    """US-32: alumnos activos con su riesgo de abandono (en riesgo primero)."""
    try:
        return list_abandonment_risk(db, user)
    except TrainerStudentError as error:
        handle_student_error(error)


@router.get("/me/students/{student_id}/evolution", response_model=TrainingEvolution)
def own_student_training_evolution(
    student_id: str,
    user: CurrentUser,
    db: DbDep,
    period: Literal["4w", "12w", "all"] = "12w",
    group_by: Literal["session", "week"] = "week",
    muscle_group: str | None = None,
) -> TrainingEvolution:
    """US-30: progreso del alumno (progresión, adherencia, esfuerzo y puntos a revisar)."""
    try:
        return get_training_evolution(db, user, student_id, period, group_by, muscle_group)
    except TrainerStudentError as error:
        handle_student_error(error)


@router.post("/me/students/{student_id}/termination", response_model=StudentTerminationResult)
def own_student_termination(
    student_id: str,
    payload: StudentTerminationRequest,
    user: CurrentUser,
    db: DbDep,
    day: Annotated[date | None, Query(alias="date", description="Fecha local del entrenador (hoy).")] = None,
) -> StudentTerminationResult:
    """US-35: da de baja al alumno con el motivo indicado; libera el cupo y revoca accesos."""
    try:
        return terminate_student(db, user, student_id, payload, day or date.today())
    except TrainerStudentError as error:
        handle_student_error(error)


@router.get("/me/students/{student_id}", response_model=TrainerStudentDetail)
def own_active_student_detail(
    student_id: str, user: CurrentUser, db: DbDep
) -> TrainerStudentDetail:
    try:
        return get_trainer_student_detail(db, user, student_id)
    except TrainerStudentError as error:
        handle_student_error(error)


@router.get("/me/safety-alerts", response_model=list[SafetyAlertView])
def own_safety_alerts(
    user: CurrentUser,
    db: DbDep,
    status_filter: Annotated[SafetyAlertStatus | None, Query(alias="status")] = None,
    student_id: Annotated[str | None, Query()] = None,
) -> list[SafetyAlertView]:
    """US-29: lista alertas de seguridad de los vínculos ACTIVE del entrenador."""
    try:
        return list_trainer_safety_alerts(
            db,
            user,
            status_filter=status_filter,
            student_id=student_id,
        )
    except SafetyAlertError as error:
        handle_safety_alert_error(error)


@router.get("/me/students/{student_id}/safety-alerts", response_model=list[SafetyAlertView])
def own_active_student_safety_alerts(
    student_id: str,
    user: CurrentUser,
    db: DbDep,
    status_filter: Annotated[SafetyAlertStatus | None, Query(alias="status")] = None,
) -> list[SafetyAlertView]:
    """US-29: lista alertas de seguridad de un alumno activo específico."""
    try:
        return list_trainer_student_safety_alerts(
            db,
            user,
            student_id,
            status_filter=status_filter,
        )
    except SafetyAlertError as error:
        handle_safety_alert_error(error)


@router.patch("/me/safety-alerts/{alert_id}/review", response_model=SafetyAlertView)
def review_own_safety_alert(
    alert_id: str,
    payload: SafetyAlertReviewRequest,
    user: CurrentUser,
    db: DbDep,
) -> SafetyAlertView:
    """US-29 (CA-4): marca una alerta de seguridad como revisada con acción tomada y nota opcional."""
    try:
        return review_safety_alert(db, user, alert_id, payload)
    except SafetyAlertError as error:
        handle_safety_alert_error(error)


@router.get("/me/profile", response_model=TrainerProfileResponse)
def own_profile(user: CurrentUser, db: DbDep) -> TrainerProfileResponse:
    try:
        return profile_response(db, get_or_create_profile(db, user))
    except TrainerProfileError as error:
        handle_error(error)


@router.put("/me/profile", response_model=TrainerProfileResponse)
def save_own_profile(payload: TrainerProfileUpdate, user: CurrentUser, db: DbDep) -> TrainerProfileResponse:
    try:
        return profile_response(db, update_profile(db, user, payload))
    except TrainerProfileError as error:
        handle_error(error)


@router.get("/{trainer_id}/profile", response_model=TrainerProfileResponse)
def published_profile(trainer_id: str, _: CurrentUser, db: DbDep) -> TrainerProfileResponse:
    try:
        return profile_response(db, get_published_profile(db, trainer_id))
    except TrainerProfileError as error:
        handle_error(error)


@router.patch("/me/quota", response_model=TrainerQuotaResponse)
def save_own_quota(payload: TrainerQuotaUpdate, user: CurrentUser, db: DbDep) -> TrainerQuotaResponse:
    try:
        return TrainerQuotaResponse(**quota_summary(db, update_quota(db, user, payload)))
    except TrainerProfileError as error:
        handle_error(error)


@router.get("/me/plans", response_model=list[TrainingPlanResponse])
def own_plans(user: CurrentUser, db: DbDep) -> list[TrainingPlanResponse]:
    try:
        return [TrainingPlanResponse.model_validate(plan) for plan in list_own_plans(db, user)]
    except TrainerProfileError as error:
        handle_error(error)


@router.post("/me/plans", response_model=TrainingPlanResponse, status_code=status.HTTP_201_CREATED)
def publish_plan(payload: TrainingPlanCreate, user: CurrentUser, db: DbDep) -> TrainingPlanResponse:
    try:
        return TrainingPlanResponse.model_validate(create_plan(db, user, payload))
    except TrainerProfileError as error:
        handle_error(error)


@router.put("/me/plans/{plan_id}", response_model=TrainingPlanResponse)
def edit_plan(plan_id: str, payload: TrainingPlanUpdate, user: CurrentUser, db: DbDep) -> TrainingPlanResponse:
    try:
        return TrainingPlanResponse.model_validate(update_plan(db, user, plan_id, payload))
    except TrainerProfileError as error:
        handle_error(error)


@router.post("/me/plans/{plan_id}/archive", response_model=TrainingPlanResponse)
def archive_own_plan(plan_id: str, user: CurrentUser, db: DbDep) -> TrainingPlanResponse:
    try:
        return TrainingPlanResponse.model_validate(archive_plan(db, user, plan_id))
    except TrainerProfileError as error:
        handle_error(error)


@router.get("/{trainer_id}/plans", response_model=list[TrainingPlanResponse])
def published_plans(trainer_id: str, _: CurrentUser, db: DbDep) -> list[TrainingPlanResponse]:
    try:
        return [TrainingPlanResponse.model_validate(plan) for plan in list_published_plans(db, trainer_id)]
    except TrainerProfileError as error:
        handle_error(error)
