"""Cálculo puro del vencimiento y estado de una suscripción (US-34).

La suscripción no se persiste: el vínculo activo es la suscripción y su vencimiento
se deriva de la fecha de inicio y de los meses de pagos confirmados (research.md R1).
Sin I/O, para que US-35 y US-71 lo reutilicen.
"""

import calendar
from datetime import date

DUE_SOON_DAYS = 5
# El primer mes se considera abonado al aceptar al alumno (Clarificaciones 2026-11-16).
INCLUDED_FIRST_MONTHS = 1

STATUS_ORDER = {"VENCIDA": 0, "POR_VENCER": 1, "AL_DIA": 2}


def add_months(start: date, months: int) -> date:
    """Suma meses desde ``start`` recortando al último día del mes destino (31/01 + 1 → 28/02)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def compute_due_date(start_date: date, months_paid: int) -> date:
    """Vencimiento = inicio + (primer mes + meses pagados), calculado siempre desde el inicio (R2)."""
    return add_months(start_date, INCLUDED_FIRST_MONTHS + months_paid)


def subscription_status(due_date: date, today: date) -> tuple[str, int]:
    """Devuelve (estado, días hasta el vencimiento). El día del vencimiento todavía está cubierto."""
    days_until_due = (due_date - today).days
    if days_until_due < 0:
        return "VENCIDA", days_until_due
    if days_until_due <= DUE_SOON_DAYS:
        return "POR_VENCER", days_until_due
    return "AL_DIA", days_until_due


def current_date() -> date:
    """"Hoy" del servidor para reglas que no reciben la fecha local del cliente (bloqueo de FR-006).

    Es una función aparte para que las pruebas puedan simular otra fecha.
    """
    return date.today()


MAX_CLIENT_DATE_DRIFT_DAYS = 1
DATE_DRIFT_MESSAGE = "La fecha local indicada difiere demasiado de la fecha del servidor."


def resolve_local_date(requested: date | None, server_today: date | None = None) -> date:
    """Valida que la fecha local del cliente no difiera más de ±1 día de la fecha del servidor."""
    today = server_today if server_today is not None else current_date()
    if requested is None:
        return today
    if abs((requested - today).days) > MAX_CLIENT_DATE_DRIFT_DAYS:
        raise ValueError(DATE_DRIFT_MESSAGE)
    return requested


def validated_local_date(
    requested: date | None,
    error_factory,
    *,
    allow_none: bool = False,
    field: str = "date",
) -> date | None:
    if requested is None and allow_none:
        return None
    try:
        return resolve_local_date(requested)
    except ValueError as error:
        raise error_factory(
            422,
            str(error),
            [{"field": field, "message": str(error)}],
        ) from error
