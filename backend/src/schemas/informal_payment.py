"""Esquemas de pagos informales y estado de suscripciones (US-34)."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SubscriptionStatus = Literal["AL_DIA", "POR_VENCER", "VENCIDA"]
PaymentMethod = Literal["EFECTIVO", "TRANSFERENCIA", "OTRO"]
PaymentStatus = Literal["PENDIENTE_CONFIRMACION", "CONFIRMADO", "RECHAZADO", "ANULADO"]

PAYMENT_METHOD_VALUES = ("EFECTIVO", "TRANSFERENCIA", "OTRO")
MAX_AMOUNT = Decimal("9999999.99")
MIN_MONTHS = 1
MAX_MONTHS = 12
NOTE_MAX_LENGTH = 500
VOID_REASON_MIN_LENGTH = 5
VOID_REASON_MAX_LENGTH = 500

PAID_ON_REQUIRED_MESSAGE = "Ingresá la fecha del pago."
PAID_ON_FUTURE_MESSAGE = "La fecha del pago no puede ser futura."
AMOUNT_REQUIRED_MESSAGE = "Ingresá el monto del pago."
AMOUNT_POSITIVE_MESSAGE = "El monto debe ser mayor a cero."
AMOUNT_MAX_MESSAGE = "El monto no puede superar $9.999.999,99."
AMOUNT_DECIMALS_MESSAGE = "El monto admite hasta 2 decimales."
METHOD_REQUIRED_MESSAGE = "Elegí el medio de pago."
MONTHS_RANGE_MESSAGE = "El período debe ser de 1 a 12 meses."
NOTE_LENGTH_MESSAGE = "La nota admite hasta 500 caracteres."
VOID_REASON_MESSAGE = "Indicá el motivo de la anulación (entre 5 y 500 caracteres)."


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class PaymentCreate(BaseModel):
    # Opcionales con validate_default para informar todos los faltantes con mensaje propio (escenario 3).
    paid_on: date | None = Field(default=None, validate_default=True)
    amount: Decimal | None = Field(default=None, validate_default=True)
    method: str | None = Field(default=None, validate_default=True)
    months_covered: int | None = Field(default=None, validate_default=True)
    note: str | None = None
    replaces_payment_id: str | None = None

    @field_validator("paid_on", mode="before")
    @classmethod
    def require_paid_on(cls, value: object) -> object:
        value = _blank_to_none(value)
        if value is None:
            raise ValueError(PAID_ON_REQUIRED_MESSAGE)
        return value

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        value = _blank_to_none(value)
        # bool se descarta acá: Decimal("True") falla y devuelve el mismo mensaje.
        if value is None:
            raise ValueError(AMOUNT_REQUIRED_MESSAGE)
        try:
            amount = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            raise ValueError(AMOUNT_REQUIRED_MESSAGE) from None
        if not amount.is_finite():
            raise ValueError(AMOUNT_REQUIRED_MESSAGE)
        if amount <= 0:
            raise ValueError(AMOUNT_POSITIVE_MESSAGE)
        if amount > MAX_AMOUNT:
            raise ValueError(AMOUNT_MAX_MESSAGE)
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError(AMOUNT_DECIMALS_MESSAGE)
        return amount.quantize(Decimal("0.01"))

    @field_validator("method", mode="before")
    @classmethod
    def validate_method(cls, value: object) -> str:
        value = _blank_to_none(value)
        if not isinstance(value, str) or value.strip().upper() not in PAYMENT_METHOD_VALUES:
            raise ValueError(METHOD_REQUIRED_MESSAGE)
        return value.strip().upper()

    @field_validator("months_covered", mode="before")
    @classmethod
    def validate_months(cls, value: object) -> int:
        value = _blank_to_none(value)
        if isinstance(value, bool) or value is None:
            raise ValueError(MONTHS_RANGE_MESSAGE)
        try:
            months = int(value)
        except (TypeError, ValueError):
            raise ValueError(MONTHS_RANGE_MESSAGE) from None
        if str(months) != str(value).strip() and not isinstance(value, int):
            raise ValueError(MONTHS_RANGE_MESSAGE)
        if not MIN_MONTHS <= months <= MAX_MONTHS:
            raise ValueError(MONTHS_RANGE_MESSAGE)
        return months

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> object:
        value = _blank_to_none(value)
        if value is None:
            return None
        value = str(value).strip()
        if len(value) > NOTE_MAX_LENGTH:
            raise ValueError(NOTE_LENGTH_MESSAGE)
        return value

    @field_validator("replaces_payment_id", mode="before")
    @classmethod
    def normalize_replaces(cls, value: object) -> object:
        value = _blank_to_none(value)
        return value.strip() if isinstance(value, str) else value


class PaymentVoidRequest(BaseModel):
    reason: str | None = Field(default=None, validate_default=True)

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        value = value.strip() if isinstance(value, str) else ""
        if not VOID_REASON_MIN_LENGTH <= len(value) <= VOID_REASON_MAX_LENGTH:
            raise ValueError(VOID_REASON_MESSAGE)
        return value


class SubscriptionSummary(BaseModel):
    relationship_id: str
    student_id: str
    student_name: str
    plan_id: str
    plan_title: str
    agreed_monthly_price: Decimal
    currency: str
    start_date: date
    months_paid: int
    due_date: date
    days_until_due: int
    status: SubscriptionStatus
    last_payment_on: date | None


class PaymentView(BaseModel):
    id: str
    paid_on: date
    amount: Decimal
    currency: str
    method: PaymentMethod
    months_covered: int
    status: PaymentStatus
    note: str | None
    registered_by_name: str
    created_at: datetime
    voided_at: datetime | None
    voided_by_name: str | None
    void_reason: str | None
    replaces_payment_id: str | None
    replaced_by_payment_id: str | None


class PaymentHistory(BaseModel):
    subscription: SubscriptionSummary
    payments: list[PaymentView]


class PaymentMutationResult(BaseModel):
    subscription: SubscriptionSummary
    payment: PaymentView
