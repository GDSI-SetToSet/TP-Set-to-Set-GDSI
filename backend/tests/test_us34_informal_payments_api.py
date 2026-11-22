"""US-34: registrar pagos informales y controlar el estado de las suscripciones (API)."""

from datetime import date

import pytest
from sqlalchemy import select

from backend.src.models.informal_payment import (
    PAYMENT_DELETE_FORBIDDEN,
    InformalPayment,
)
from backend.src.models.training_relationship import TrainingRelationship
from backend.tests.test_trainer_student_api import (
    create_relationship,
    register_and_login,
)

SUBSCRIPTIONS = "/api/v1/trainers/me/subscriptions"
TODAY = "2026-11-10"
START = date(2026, 10, 1)  # primer vencimiento: 2026-11-01


def payments_path(student_id: str) -> str:
    return f"/api/v1/trainers/me/students/{student_id}/payments"


def void_path(payment_id: str) -> str:
    return f"/api/v1/trainers/me/payments/{payment_id}/void"


def set_start(sessions, relationship_id: str, start: date) -> None:
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        relationship.start_date = start
        db.commit()


def payment_body(**overrides) -> dict:
    body = {"paid_on": TODAY, "amount": "12500.00", "method": "TRANSFERENCIA", "months_covered": 1}
    body.update(overrides)
    return body


@pytest.fixture
def trainer_with_student(client):
    api, sessions = client
    headers = register_and_login(api, "coach@example.com", "TRAINER")
    register_and_login(api, "alumna1@example.com", "STUDENT")
    relationship_id, student_id = create_relationship(sessions, "coach@example.com", "alumna1@example.com")
    set_start(sessions, relationship_id, START)
    return api, sessions, headers, relationship_id, student_id


def register(api, headers, student_id, **overrides):
    return api.post(payments_path(student_id), params={"date": TODAY}, json=payment_body(**overrides), headers=headers)


# Escenario 1 -----------------------------------------------------------------------------


def test_lists_subscriptions_with_status_order_and_filter(client):
    api, sessions = client
    headers = register_and_login(api, "coach@example.com", "TRAINER")
    starts = {
        "vencida@example.com": date(2026, 9, 1),  # vence 2026-10-01 → VENCIDA
        "porvencer@example.com": date(2026, 10, 12),  # vence 2026-11-12 → POR_VENCER (2 días)
        "aldia@example.com": date(2026, 11, 1),  # vence 2026-12-01 → AL_DIA
    }
    for email, start in starts.items():
        register_and_login(api, email, "STUDENT")
        relationship_id, _ = create_relationship(sessions, "coach@example.com", email)
        set_start(sessions, relationship_id, start)

    response = api.get(SUBSCRIPTIONS, params={"date": TODAY}, headers=headers)

    assert response.status_code == 200
    items = response.json()
    assert [item["status"] for item in items] == ["VENCIDA", "POR_VENCER", "AL_DIA"]
    assert [item["due_date"] for item in items] == ["2026-10-01", "2026-11-12", "2026-12-01"]
    assert items[0]["days_until_due"] == -40
    assert items[1]["days_until_due"] == 2
    assert items[0]["plan_title"] == "Plan Premium"
    assert items[0]["agreed_monthly_price"] == "12500.00"
    assert items[0]["currency"] == "ARS"
    assert items[0]["student_name"] == "Valeria Alumna"
    assert items[0]["months_paid"] == 0
    assert items[0]["last_payment_on"] is None

    filtered = api.get(SUBSCRIPTIONS, params={"date": TODAY, "status": "POR_VENCER"}, headers=headers)
    assert [item["due_date"] for item in filtered.json()] == ["2026-11-12"]


def test_newly_accepted_student_is_up_to_date_for_one_month(client):
    api, sessions = client
    headers = register_and_login(api, "coach@example.com", "TRAINER")
    register_and_login(api, "nueva@example.com", "STUDENT")
    relationship_id, _ = create_relationship(sessions, "coach@example.com", "nueva@example.com")
    set_start(sessions, relationship_id, date(2026, 11, 10))

    item = api.get(SUBSCRIPTIONS, params={"date": TODAY}, headers=headers).json()[0]

    assert item["status"] == "AL_DIA"
    assert item["due_date"] == "2026-12-10"


def test_empty_list_and_excludes_terminated_and_foreign_students(client):
    api, sessions = client
    headers = register_and_login(api, "coach@example.com", "TRAINER")
    assert api.get(SUBSCRIPTIONS, headers=headers).json() == []

    register_and_login(api, "otro-coach@example.com", "TRAINER")
    register_and_login(api, "ajena@example.com", "STUDENT")
    register_and_login(api, "baja@example.com", "STUDENT")
    create_relationship(sessions, "otro-coach@example.com", "ajena@example.com")
    create_relationship(sessions, "coach@example.com", "baja@example.com", status="TERMINATED")

    assert api.get(SUBSCRIPTIONS, headers=headers).json() == []


# Escenario 2 -----------------------------------------------------------------------------


def test_payment_extends_from_previous_due_date_even_when_overdue(trainer_with_student):
    api, _, headers, _, student_id = trainer_with_student
    before = api.get(SUBSCRIPTIONS, params={"date": TODAY}, headers=headers).json()[0]
    assert before["status"] == "VENCIDA"

    response = register(api, headers, student_id, months_covered=1)

    assert response.status_code == 201
    body = response.json()
    assert body["subscription"]["due_date"] == "2026-12-01"  # no 2026-12-10
    assert body["subscription"]["status"] == "AL_DIA"
    assert body["subscription"]["months_paid"] == 1
    assert body["subscription"]["last_payment_on"] == TODAY
    payment = body["payment"]
    assert payment["status"] == "CONFIRMADO"
    assert payment["currency"] == "ARS"
    assert payment["amount"] == "12500.00"
    assert payment["registered_by_name"] == "Entrenador Principal"

    second = register(api, headers, student_id, months_covered=3, method="efectivo", amount="30000")
    assert second.status_code == 201
    assert second.json()["subscription"]["due_date"] == "2027-03-01"
    assert second.json()["payment"]["method"] == "EFECTIVO"


# Escenario 3 -----------------------------------------------------------------------------


def test_missing_date_and_amount_are_reported_together(trainer_with_student):
    api, sessions, headers, _, student_id = trainer_with_student

    response = api.post(
        payments_path(student_id),
        params={"date": TODAY},
        json={"method": "EFECTIVO", "months_covered": 1, "amount": ""},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    errors = {error["field"]: error["message"] for error in response.json()["errors"]}
    assert errors["paid_on"] == "Ingresá la fecha del pago."
    assert errors["amount"] == "Ingresá el monto del pago."
    with sessions() as db:
        assert db.scalar(select(InformalPayment.id)) is None


@pytest.mark.parametrize(
    ("overrides", "field", "message"),
    [
        ({"amount": "0"}, "amount", "El monto debe ser mayor a cero."),
        ({"amount": "-10"}, "amount", "El monto debe ser mayor a cero."),
        ({"amount": "10000000"}, "amount", "El monto no puede superar $9.999.999,99."),
        ({"amount": "10.555"}, "amount", "El monto admite hasta 2 decimales."),
        ({"amount": "abc"}, "amount", "Ingresá el monto del pago."),
        ({"months_covered": 0}, "months_covered", "El período debe ser de 1 a 12 meses."),
        ({"months_covered": 13}, "months_covered", "El período debe ser de 1 a 12 meses."),
        ({"months_covered": 1.5}, "months_covered", "El período debe ser de 1 a 12 meses."),
        ({"method": "TARJETA"}, "method", "Elegí el medio de pago."),
        ({"method": None}, "method", "Elegí el medio de pago."),
        ({"note": "x" * 501}, "note", "La nota admite hasta 500 caracteres."),
    ],
)
def test_invalid_payment_fields_are_rejected(trainer_with_student, overrides, field, message):
    api, _, headers, _, student_id = trainer_with_student

    response = register(api, headers, student_id, **overrides)

    assert response.status_code == 422
    errors = {error["field"]: error["message"] for error in response.json()["errors"]}
    assert errors[field] == message


def test_future_payment_date_is_rejected(trainer_with_student):
    api, _, headers, _, student_id = trainer_with_student

    response = register(api, headers, student_id, paid_on="2026-11-11")

    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "paid_on", "message": "La fecha del pago no puede ser futura."}
    ]


def test_note_is_trimmed_and_blank_note_is_null(trainer_with_student):
    api, _, headers, _, student_id = trainer_with_student
    assert register(api, headers, student_id, note="  Pagó en efectivo  ").json()["payment"]["note"] == (
        "Pagó en efectivo"
    )
    assert register(api, headers, student_id, note="   ").json()["payment"]["note"] is None


# Escenario 5 -----------------------------------------------------------------------------


def test_history_includes_voided_payments_and_void_recalculates_due_date(trainer_with_student):
    api, _, headers, _, student_id = trainer_with_student
    first = register(api, headers, student_id, paid_on="2026-11-02", months_covered=1).json()["payment"]
    register(api, headers, student_id, paid_on=TODAY, months_covered=2)

    voided = api.post(
        void_path(first["id"]), params={"date": TODAY}, json={"reason": "  Monto mal cargado  "}, headers=headers
    )

    assert voided.status_code == 200
    assert voided.json()["payment"]["status"] == "ANULADO"
    assert voided.json()["payment"]["void_reason"] == "Monto mal cargado"
    assert voided.json()["payment"]["voided_by_name"] == "Entrenador Principal"
    assert voided.json()["payment"]["voided_at"] is not None
    assert voided.json()["subscription"]["months_paid"] == 2
    assert voided.json()["subscription"]["due_date"] == "2027-01-01"

    history = api.get(payments_path(student_id), params={"date": TODAY}, headers=headers)
    assert history.status_code == 200
    payments = history.json()["payments"]
    assert [p["paid_on"] for p in payments] == [TODAY, "2026-11-02"]
    assert [p["status"] for p in payments] == ["CONFIRMADO", "ANULADO"]
    assert history.json()["subscription"]["due_date"] == "2027-01-01"
    assert history.json()["subscription"]["last_payment_on"] == TODAY


@pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "abc"}, {"reason": "x" * 501}])
def test_void_requires_reason(trainer_with_student, body):
    api, _, headers, _, student_id = trainer_with_student
    payment = register(api, headers, student_id).json()["payment"]

    response = api.post(void_path(payment["id"]), json=body, headers=headers)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "reason"


def test_double_void_conflicts(trainer_with_student):
    api, _, headers, _, student_id = trainer_with_student
    payment = register(api, headers, student_id).json()["payment"]
    assert api.post(void_path(payment["id"]), json={"reason": "Error de carga"}, headers=headers).status_code == 200

    again = api.post(void_path(payment["id"]), json={"reason": "Error de carga"}, headers=headers)

    assert again.status_code == 409
    assert again.json()["detail"] == "El pago ya está anulado."


def test_payments_cannot_be_deleted(trainer_with_student):
    api, sessions, headers, _, student_id = trainer_with_student
    payment = register(api, headers, student_id).json()["payment"]

    assert api.delete(void_path(payment["id"]).removesuffix("/void"), headers=headers).status_code in (404, 405)
    assert api.delete(payments_path(student_id), headers=headers).status_code == 405
    with sessions() as db:
        record = db.get(InformalPayment, payment["id"])
        db.delete(record)
        with pytest.raises(RuntimeError, match=PAYMENT_DELETE_FORBIDDEN):
            db.flush()


# Escenario 6 -----------------------------------------------------------------------------


def test_reissue_references_voided_payment_once(trainer_with_student):
    api, _, headers, _, student_id = trainer_with_student
    original = register(api, headers, student_id, amount="1250.00").json()["payment"]
    api.post(void_path(original["id"]), json={"reason": "Faltó un cero"}, headers=headers)

    corrected = register(api, headers, student_id, amount="12500.00", replaces_payment_id=original["id"])

    assert corrected.status_code == 201
    assert corrected.json()["payment"]["replaces_payment_id"] == original["id"]
    assert corrected.json()["subscription"]["months_paid"] == 1
    history = api.get(payments_path(student_id), headers=headers).json()["payments"]
    by_id = {p["id"]: p for p in history}
    assert by_id[original["id"]]["replaced_by_payment_id"] == corrected.json()["payment"]["id"]

    twice = register(api, headers, student_id, replaces_payment_id=original["id"])
    assert twice.status_code == 409


def test_reissue_requires_voided_payment_of_same_student(client):
    api, sessions = client
    headers = register_and_login(api, "coach@example.com", "TRAINER")
    register_and_login(api, "a@example.com", "STUDENT")
    register_and_login(api, "b@example.com", "STUDENT")
    _, student_a = create_relationship(sessions, "coach@example.com", "a@example.com")
    _, student_b = create_relationship(sessions, "coach@example.com", "b@example.com")
    payment_a = api.post(payments_path(student_a), json=payment_body(paid_on="2026-01-01"), headers=headers)
    payment_id = payment_a.json()["payment"]["id"]

    not_voided = api.post(
        payments_path(student_a),
        json=payment_body(paid_on="2026-01-01", replaces_payment_id=payment_id),
        headers=headers,
    )
    assert not_voided.status_code == 422
    assert not_voided.json()["errors"][0]["field"] == "replaces_payment_id"

    api.post(void_path(payment_id), json={"reason": "Alumno equivocado"}, headers=headers)
    other_student = api.post(
        payments_path(student_b),
        json=payment_body(paid_on="2026-01-01", replaces_payment_id=payment_id),
        headers=headers,
    )
    assert other_student.status_code == 422

    missing = api.post(
        payments_path(student_b),
        json=payment_body(paid_on="2026-01-01", replaces_payment_id="no-existe"),
        headers=headers,
    )
    assert missing.status_code == 422


# Autorización ----------------------------------------------------------------------------


def test_requires_authentication(client):
    api, _ = client
    assert api.get(SUBSCRIPTIONS).status_code == 401
    assert api.post(void_path("x"), json={"reason": "Motivo válido"}).status_code == 401


def test_student_role_is_forbidden(trainer_with_student):
    api, _, _, _, student_id = trainer_with_student
    student_headers = register_and_login(api, "solo-alumna@example.com", "STUDENT")

    for response in (
        api.get(SUBSCRIPTIONS, headers=student_headers),
        api.get(payments_path(student_id), headers=student_headers),
        api.post(payments_path(student_id), json=payment_body(), headers=student_headers),
        api.post(void_path("x"), json={"reason": "Motivo válido"}, headers=student_headers),
    ):
        assert response.status_code == 403
        assert response.headers["content-type"].startswith("application/problem+json")


def test_foreign_trainer_gets_not_found(trainer_with_student):
    api, _, headers, _, student_id = trainer_with_student
    payment = register(api, headers, student_id).json()["payment"]
    other = register_and_login(api, "intruso@example.com", "TRAINER")

    assert api.get(payments_path(student_id), headers=other).status_code == 404
    assert api.post(payments_path(student_id), json=payment_body(), headers=other).status_code == 404
    assert api.post(void_path(payment["id"]), json={"reason": "Motivo válido"}, headers=other).status_code == 404
    assert api.post(void_path("no-existe"), json={"reason": "Motivo válido"}, headers=headers).status_code == 404


def test_terminated_relationship_hides_history_and_blocks_void(trainer_with_student):
    api, sessions, headers, relationship_id, student_id = trainer_with_student
    payment = register(api, headers, student_id).json()["payment"]
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()

    assert api.get(payments_path(student_id), headers=headers).status_code == 404
    assert api.post(void_path(payment["id"]), json={"reason": "Motivo válido"}, headers=headers).status_code == 404
