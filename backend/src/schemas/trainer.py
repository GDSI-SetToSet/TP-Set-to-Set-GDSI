import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

PHONE_PATTERN = re.compile(r"^\+?[0-9]{8,15}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
DEFAULT_CURRENCY = "ARS"
PLAN_TITLE_MAX_LENGTH = 100
PLAN_MIN_PRICE = Decimal(0)
PLAN_MAX_PRICE = Decimal(1000000)
REQUIRED_FIELD_MESSAGE = "Este campo es obligatorio"
PRICE_RANGE_MESSAGE = "La tarifa debe estar entre $0 y $1.000.000"
MIN_QUOTA = 0
MAX_QUOTA = 100
QUOTA_RANGE_MESSAGE = "Los cupos deben estar entre 0 y 100"


class TrainerProfileUpdate(BaseModel):
    full_name: str | None = None
    contact_phone: str | None = None
    specialty: str | None = None
    bio: str | None = None
    certifications: str | None = None

    @field_validator("full_name", "specialty", "bio", "certifications")
    @classmethod
    def reject_empty_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Este campo no puede estar vacío.")
        return value.strip() if value is not None else None

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is not None and not PHONE_PATTERN.fullmatch(value):
            raise ValueError("Ingresá un teléfono válido de 8 a 15 dígitos (puede iniciar con +).")
        return value


class TrainerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str | None
    contact_phone: str | None
    specialty: str | None
    status: str
    bio: str | None
    certifications: str | None
    max_students: int
    active_students_count: int = 0
    available_slots: int = 0
    has_available_quota: bool = False
    created_at: datetime
    updated_at: datetime


class TrainerQuotaUpdate(BaseModel):
    # Si no se indica el tope, se guarda 0: el perfil queda "Sin cupos disponibles" (US-04, escenario 2).
    max_students: int | None = Field(default=None, validate_default=True)

    @field_validator("max_students")
    @classmethod
    def validate_quota(cls, value: int | None) -> int:
        if value is None:
            return MIN_QUOTA
        if not MIN_QUOTA <= value <= MAX_QUOTA:
            raise PydanticCustomError("quota_range", QUOTA_RANGE_MESSAGE)
        return value


class TrainerQuotaResponse(BaseModel):
    max_students: int
    active_students: int
    available_slots: int
    has_available_quota: bool


# PydanticCustomError evita el prefijo "Value error," para que el mensaje llegue tal cual al usuario (US-03).
def validate_plan_title(value: str | None) -> str:
    if value is None or not value.strip():
        raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
    if len(value.strip()) > PLAN_TITLE_MAX_LENGTH:
        raise PydanticCustomError("too_long", "El título admite hasta 100 caracteres")
    return value.strip()


def validate_plan_price(value: Decimal | None) -> Decimal:
    if value is None:
        raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
    if not PLAN_MIN_PRICE <= value <= PLAN_MAX_PRICE:
        raise PydanticCustomError("price_range", PRICE_RANGE_MESSAGE)
    return value


def validate_currency(value: str) -> str:
    code = value.strip().upper()
    if not CURRENCY_PATTERN.fullmatch(code):
        raise PydanticCustomError("currency", "La moneda debe ser un código de 3 letras (ej. ARS)")
    return code


def normalize_description(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


class TrainingPlanCreate(BaseModel):
    title: str | None = Field(default=None, validate_default=True)
    description: str | None = None
    monthly_price: Decimal | None = Field(default=None, validate_default=True)
    currency: str = DEFAULT_CURRENCY

    _title = field_validator("title")(validate_plan_title)
    _price = field_validator("monthly_price")(validate_plan_price)
    _currency = field_validator("currency")(validate_currency)
    _description = field_validator("description")(normalize_description)


class TrainingPlanUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    monthly_price: Decimal | None = None
    currency: str | None = None

    # Solo se validan los campos enviados: enviar null o vacío en título/tarifa es un error.
    _title = field_validator("title")(validate_plan_title)
    _price = field_validator("monthly_price")(validate_plan_price)
    _description = field_validator("description")(normalize_description)

    @field_validator("currency")
    @classmethod
    def validate_optional_currency(cls, value: str | None) -> str:
        if value is None:
            raise PydanticCustomError("required", REQUIRED_FIELD_MESSAGE)
        return validate_currency(value)


class TrainingPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    trainer_id: str
    title: str
    description: str | None
    monthly_price: float
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
