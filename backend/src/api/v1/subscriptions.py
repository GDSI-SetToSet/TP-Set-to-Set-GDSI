"""Rutas de la suscripción vista por el alumno y del comprobante de pago (US-71)."""

from datetime import date
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import ValidationError

from backend.src.api.errors import field_name
from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.core.storage import sanitize_filename
from backend.src.models.user import User
from backend.src.schemas.informal_payment import (
    PaymentCreate,
    PaymentHistory,
    PaymentMutationResult,
    SubscriptionSummary,
)
from backend.src.services.informal_payment_service import PaymentError
from backend.src.services.student_subscription_service import (
    get_student_payment_history,
    list_student_subscriptions,
    receipt_for_download,
    report_payment,
)
from backend.src.services.subscription_service import validated_local_date

router = APIRouter(prefix=API_V1_PREFIX, tags=["subscriptions"])
CurrentUser = Annotated[User, Depends(get_current_user)]
LocalDate = Annotated[date | None, Query(alias="date", description="Fecha local del alumno (hoy).")]


def handle_error(error: PaymentError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


def validation_problem(error: ValidationError) -> HTTPException:
    """El formulario multipart se valida con PaymentCreate; se responde como el resto de la API (RFC 7807)."""
    errors = []
    for item in error.errors():
        value_error = (item.get("ctx") or {}).get("error")
        message = str(value_error) if isinstance(value_error, ValueError) else item["msg"]
        errors.append({"field": field_name(tuple(item["loc"])), "message": message})
    return HTTPException(
        status_code=422, detail={"detail": "Los datos del pago no son válidos.", "errors": errors}
    )


@router.get("/students/me/subscriptions", response_model=list[SubscriptionSummary])
def own_subscriptions(user: CurrentUser, db: DbDep, day: LocalDate = None) -> list[SubscriptionSummary]:
    """US-71 escenarios 1, 2 y 4: vencimiento y estado de cada vínculo activo."""
    try:
        resolved_day = validated_local_date(day, PaymentError)
        return list_student_subscriptions(db, user, resolved_day)
    except PaymentError as error:
        handle_error(error)


@router.get("/students/me/subscriptions/{relationship_id}/payments", response_model=PaymentHistory)
def own_subscription_payments(
    relationship_id: str, user: CurrentUser, db: DbDep, day: LocalDate = None
) -> PaymentHistory:
    """US-71 escenario 5: historial de pagos del vínculo con su estado."""
    try:
        resolved_day = validated_local_date(day, PaymentError)
        return get_student_payment_history(db, user, relationship_id, resolved_day)
    except PaymentError as error:
        handle_error(error)


@router.post(
    "/students/me/subscriptions/{relationship_id}/payments",
    response_model=PaymentMutationResult,
    status_code=status.HTTP_201_CREATED,
)
async def own_subscription_report_payment(
    relationship_id: str,
    user: CurrentUser,
    db: DbDep,
    paid_on: Annotated[str | None, Form()] = None,
    amount: Annotated[str | None, Form()] = None,
    method: Annotated[str | None, Form()] = None,
    months_covered: Annotated[str | None, Form()] = None,
    note: Annotated[str | None, Form()] = None,
    receipt: Annotated[UploadFile | None, File()] = None,
    day: LocalDate = None,
) -> PaymentMutationResult:
    """US-71 escenario 3: el alumno informa un pago (con comprobante opcional)."""
    try:
        resolved_day = validated_local_date(day, PaymentError)
    except PaymentError as error:
        handle_error(error)
    try:
        data = PaymentCreate(
            paid_on=paid_on, amount=amount, method=method, months_covered=months_covered, note=note
        )
    except ValidationError as error:
        raise validation_problem(error) from error
    try:
        return await report_payment(db, user, relationship_id, data, receipt, resolved_day)
    except PaymentError as error:
        handle_error(error)


@router.get("/payments/{payment_id}/receipt")
def payment_receipt(payment_id: str, user: CurrentUser, db: DbDep):
    """US-71: comprobante privado del pago; solo el alumno y el entrenador del vínculo."""
    try:
        payment, path = receipt_for_download(db, user, payment_id)
    except PaymentError as error:
        handle_error(error)
    return FileResponse(
        path=str(path),
        media_type=payment.receipt_mime_type,
        filename=sanitize_filename(payment.receipt_filename),
        headers={"X-Content-Type-Options": "nosniff"},
    )
