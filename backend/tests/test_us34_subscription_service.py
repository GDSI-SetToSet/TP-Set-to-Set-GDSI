"""US-34: reglas puras de vencimiento y estado de suscripción (data-model.md, Ejemplos del cálculo)."""

from datetime import date

import pytest

from backend.src.services.subscription_service import (
    add_months,
    compute_due_date,
    subscription_status,
)

START = date(2026, 10, 1)


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2026, 1, 31), 2, date(2026, 3, 31)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 11, 15), 2, date(2027, 1, 15)),
        (date(2026, 12, 31), 12, date(2027, 12, 31)),
        (date(2026, 5, 10), 0, date(2026, 5, 10)),
    ],
)
def test_add_months_clamps_to_month_end_without_drift(start, months, expected):
    assert add_months(start, months) == expected


def test_first_month_is_included_when_the_student_is_accepted():
    assert compute_due_date(START, 0) == date(2026, 11, 1)


def test_payments_accumulate_from_the_previous_due_date():
    assert compute_due_date(START, 1) == date(2026, 12, 1)
    assert compute_due_date(START, 1 + 3) == date(2027, 3, 1)


def test_late_payment_extends_from_previous_due_date_not_from_payment_day():
    # Vence el 1/11; paga 1 mes el 10/11 → nuevo vencimiento 1/12 (no 10/12).
    due = compute_due_date(START, 1)
    assert due == date(2026, 12, 1)
    assert subscription_status(due, date(2026, 11, 10)) == ("AL_DIA", 21)


def test_end_of_month_start_keeps_billing_day_across_payments():
    start = date(2026, 1, 31)
    assert compute_due_date(start, 0) == date(2026, 2, 28)
    assert compute_due_date(start, 1) == date(2026, 3, 31)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 20), ("AL_DIA", 12)),
        (date(2026, 10, 26), ("AL_DIA", 6)),
        (date(2026, 10, 27), ("POR_VENCER", 5)),
        (date(2026, 10, 28), ("POR_VENCER", 4)),
        (date(2026, 11, 1), ("POR_VENCER", 0)),
        (date(2026, 11, 2), ("VENCIDA", -1)),
        (date(2026, 12, 15), ("VENCIDA", -44)),
    ],
)
def test_status_thresholds(today, expected):
    assert subscription_status(date(2026, 11, 1), today) == expected
