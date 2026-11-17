"""US-71: el alumno ve su suscripción, informa pagos con comprobante y el entrenador los confirma o rechaza."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from backend.src.models.informal_payment import InformalPayment
from backend.src.models.notification import Notification
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.tests.test_trainer_student_api import create_relationship
from backend.tests.test_us60_rpe_api import (
    ASSIGNED_PATH,
    register_and_login,
    setup_routine_and_assignment,
)

TODAY = "2026-11-10"
START = date(2026, 10, 1)  # primer vencimiento 2026-11-01 → vencida el 10/11
SUBSCRIPTIONS = "/api/v1/students/me/subscriptions"
PDF = b"%PDF-1.4 comprobante de transferencia"


def payments_path(relationship_id: str) -> str:
    return f"{SUBSCRIPTIONS}/{relationship_id}/payments"


def confirm_path(payment_id: str) -> str:
    return f"/api/v1/trainers/me/payments/{payment_id}/confirm"


def reject_path(payment_id: str) -> str:
    return f"/api/v1/trainers/me/payments/{payment_id}/reject"


@pytest.fixture(autouse=True)
def receipts_dir(tmp_path, monkeypatch):
    target = tmp_path / "receipts"
    monkeypatch.setattr("backend.src.services.student_subscription_service.RECEIPTS_DIR", target)
    return target


@pytest.fixture
def setup(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    student = register_and_login(api, "alumna@example.com", "STUDENT")
    relationship_id, student_id = create_relationship(sessions, "coach@example.com", "alumna@example.com")
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).start_date = START
        db.commit()
    return api, sessions, trainer, student, relationship_id, student_id


def report(api, headers, relationship_id, receipt=None, **fields):
    data = {"paid_on": TODAY, "amount": "12500.00", "method": "TRANSFERENCIA", "months_covered": "1"}
    data.update(fields)
    files = {"receipt": receipt} if receipt else None
    return api.post(payments_path(relationship_id), params={"date": TODAY}, data=data, files=files, headers=headers)


def notifications(sessions, email: str, kind: str) -> list[Notification]:
    with sessions() as db:
        user_id = db.scalar(select(User.id).where(User.email == email))
        return list(
            db.scalars(select(Notification).where(Notification.recipient_id == user_id, Notification.type == kind))
        )


# Escenarios 1, 2 y 4 --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("today", "status", "days"),
    [("2026-10-15", "AL_DIA", 17), ("2026-10-28", "POR_VENCER", 4), (TODAY, "VENCIDA", -9)],
)
def test_student_sees_plan_due_date_and_status(setup, today, status, days):
    api, _, _, student, relationship_id, _ = setup

    response = api.get(SUBSCRIPTIONS, params={"date": today}, headers=student)

    assert response.status_code == 200
    [item] = response.json()
    assert item["relationship_id"] == relationship_id
    assert item["plan_title"] == "Plan Premium"
    assert item["trainer_name"] == "Entrenador Principal"
    assert item["trainer_id"]
    assert item["due_date"] == "2026-11-01"
    assert item["status"] == status
    assert item["days_until_due"] == days


def test_student_without_active_relationships_and_trainer_role(client):
    api, _ = client
    student = register_and_login(api, "sola@example.com", "STUDENT")
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    assert api.get(SUBSCRIPTIONS, headers=student).json() == []
    assert api.get(SUBSCRIPTIONS, headers=trainer).status_code == 403


# Escenario 3 -----------------------------------------------------------------------------


def test_reported_payment_is_pending_and_does_not_extend(setup, receipts_dir):
    api, sessions, _, student, relationship_id, _ = setup

    response = report(api, student, relationship_id, receipt=("transferencia.pdf", PDF, "application/pdf"), note="Desde mi cuenta")

    assert response.status_code == 201
    body = response.json()
    assert body["payment"]["status"] == "PENDIENTE_CONFIRMACION"
    assert body["payment"]["source"] == "STUDENT"
    assert body["payment"]["registered_by_name"] == "Valeria Alumna"
    assert body["payment"]["has_receipt"] is True
    assert body["payment"]["receipt_filename"] == "transferencia.pdf"
    assert body["subscription"]["due_date"] == "2026-11-01"
    assert body["subscription"]["status"] == "VENCIDA"
    assert body["subscription"]["pending_payment_count"] == 1
    assert len(list(receipts_dir.rglob("*.pdf"))) == 1
    [notice] = notifications(sessions, "coach@example.com", "PAYMENT_REPORTED")
    assert notice.title == "Valeria Alumna informó un pago"
    assert notice.related_entity_id == body["payment"]["id"]


def test_report_without_receipt_and_validation(setup):
    api, _, _, student, relationship_id, _ = setup
    assert report(api, student, relationship_id).json()["payment"]["has_receipt"] is False

    missing = report(api, student, relationship_id, paid_on="", amount="")
    assert missing.status_code == 422
    fields = {error["field"]: error["message"] for error in missing.json()["errors"]}
    assert fields["paid_on"] == "Ingresá la fecha del pago."
    assert fields["amount"] == "Ingresá el monto del pago."
    assert report(api, student, relationship_id, months_covered="13").status_code == 422
    future = report(api, student, relationship_id, paid_on="2026-11-11")
    assert future.json()["errors"] == [{"field": "paid_on", "message": "La fecha del pago no puede ser futura."}]


def test_receipt_type_and_size_are_validated(setup):
    api, _, _, student, relationship_id, _ = setup

    wrong_type = report(api, student, relationship_id, receipt=("nota.txt", b"hola", "text/plain"))
    script = report(api, student, relationship_id, receipt=("x.pdf", b"#!/bin/sh", "application/pdf"))

    assert wrong_type.status_code == 422
    assert wrong_type.json()["errors"][0]["field"] == "receipt"
    assert script.status_code == 422


def test_receipt_is_private_to_the_relationship(setup):
    api, _, trainer, student, relationship_id, _ = setup
    payment = report(api, student, relationship_id, receipt=("t.pdf", PDF, "application/pdf")).json()["payment"]
    receipt = f"/api/v1/payments/{payment['id']}/receipt"
    other_trainer = register_and_login(api, "otro@example.com", "TRAINER")
    other_student = register_and_login(api, "otra@example.com", "STUDENT")

    for headers in (student, trainer):
        response = api.get(receipt, headers=headers)
        assert response.status_code == 200
        assert response.content == PDF
    for headers in (other_trainer, other_student):
        assert api.get(receipt, headers=headers).status_code == 404
    no_receipt = report(api, student, relationship_id).json()["payment"]["id"]
    assert api.get(f"/api/v1/payments/{no_receipt}/receipt", headers=student).status_code == 404


def test_student_cannot_report_on_foreign_or_ended_relationship(setup):
    api, sessions, trainer, student, relationship_id, _ = setup
    register_and_login(api, "otra@example.com", "STUDENT")
    other_relationship, _ = create_relationship(sessions, "coach@example.com", "otra@example.com")

    assert report(api, student, other_relationship).status_code == 404
    assert report(api, trainer, relationship_id).status_code == 403
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()
    assert report(api, student, relationship_id).status_code == 404
    assert api.get(SUBSCRIPTIONS, headers=student).json() == []


# Escenarios 5 y 6 ------------------------------------------------------------------------


def test_trainer_confirms_reported_payment_and_due_date_extends(setup):
    api, sessions, trainer, student, relationship_id, student_id = setup
    payment = report(api, student, relationship_id).json()["payment"]
    trainer_list = api.get("/api/v1/trainers/me/subscriptions", params={"date": TODAY}, headers=trainer).json()
    assert trainer_list[0]["pending_payment_count"] == 1

    response = api.post(confirm_path(payment["id"]), params={"date": TODAY}, headers=trainer)

    assert response.status_code == 200
    body = response.json()
    assert body["payment"]["status"] == "CONFIRMADO"
    assert body["payment"]["confirmed_by_name"] == "Entrenador Principal"
    assert body["payment"]["confirmed_at"] is not None
    assert body["subscription"]["due_date"] == "2026-12-01"
    assert body["subscription"]["status"] == "AL_DIA"
    assert body["subscription"]["pending_payment_count"] == 0
    [notice] = notifications(sessions, "alumna@example.com", "PAYMENT_CONFIRMED")
    assert "vence el 01/12/2026" in notice.message
    assert api.post(confirm_path(payment["id"]), headers=trainer).status_code == 409

    history = api.get(payments_path(relationship_id), params={"date": TODAY}, headers=student).json()
    assert [p["status"] for p in history["payments"]] == ["CONFIRMADO"]
    assert history["subscription"]["due_date"] == "2026-12-01"
    trainer_history = api.get(f"/api/v1/trainers/me/students/{student_id}/payments", headers=trainer).json()
    assert trainer_history["payments"][0]["source"] == "STUDENT"


def test_trainer_rejects_with_reason(setup):
    api, sessions, trainer, student, relationship_id, _ = setup
    payment = report(api, student, relationship_id).json()["payment"]

    assert api.post(reject_path(payment["id"]), json={"reason": "no"}, headers=trainer).status_code == 422
    response = api.post(
        reject_path(payment["id"]), params={"date": TODAY}, json={"reason": "No recibí la transferencia"}, headers=trainer
    )

    assert response.status_code == 200
    body = response.json()
    assert body["payment"]["status"] == "RECHAZADO"
    assert body["payment"]["rejection_reason"] == "No recibí la transferencia"
    assert body["payment"]["rejected_by_name"] == "Entrenador Principal"
    assert body["subscription"]["due_date"] == "2026-11-01"
    [notice] = notifications(sessions, "alumna@example.com", "PAYMENT_REJECTED")
    assert "No recibí la transferencia" in notice.message
    assert api.post(confirm_path(payment["id"]), headers=trainer).status_code == 409
    void = api.post(f"/api/v1/trainers/me/payments/{payment['id']}/void", json={"reason": "Error de carga"}, headers=trainer)
    assert void.status_code == 409
    history = api.get(payments_path(relationship_id), headers=student).json()["payments"]
    assert history[0]["rejection_reason"] == "No recibí la transferencia"


def test_pending_payment_cannot_be_voided_and_only_owner_trainer_reviews(setup):
    api, _, trainer, student, relationship_id, _ = setup
    payment = report(api, student, relationship_id).json()["payment"]
    other = register_and_login(api, "otro@example.com", "TRAINER")

    void = api.post(f"/api/v1/trainers/me/payments/{payment['id']}/void", json={"reason": "Error de carga"}, headers=trainer)
    assert void.status_code == 409
    assert void.json()["detail"] == "Solo se pueden anular pagos confirmados."
    assert api.post(confirm_path(payment["id"]), headers=other).status_code == 404
    assert api.post(reject_path(payment["id"]), json={"reason": "Motivo válido"}, headers=other).status_code == 404
    assert api.post(confirm_path(payment["id"]), headers=student).status_code == 403
    assert api.post(confirm_path("no-existe"), headers=trainer).status_code == 404


# FR-006: bloqueo con la suscripción vencida ----------------------------------------------


def test_expired_subscription_blocks_new_sessions_until_confirmation(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe@example.com", "TRAINER")
    student = register_and_login(api, "student71@example.com", "STUDENT")
    _, relationship_id, _ = setup_routine_and_assignment(api, sessions, trainer, "student71@example.com")
    future = date.today() + timedelta(days=45)  # el primer mes ya venció
    monkeypatch.setattr("backend.src.services.student_subscription_service.current_date", lambda: future)
    start = f"{ASSIGNED_PATH}/workout-sessions"

    blocked = api.post(start, headers=student, json={"day_name": "Día 1"})
    assert blocked.status_code == 409
    assert "suscripción está vencida" in blocked.json()["detail"]

    payment = report(api, student, relationship_id)
    assert payment.status_code == 201
    assert api.post(start, headers=student, json={"day_name": "Día 1"}).status_code == 409  # pendiente no desbloquea

    api.post(confirm_path(payment.json()["payment"]["id"]), headers=trainer)
    assert api.post(start, headers=student, json={"day_name": "Día 1"}).status_code == 201


def test_active_subscription_does_not_block(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe@example.com", "TRAINER")
    student = register_and_login(api, "student71b@example.com", "STUDENT")
    setup_routine_and_assignment(api, sessions, trainer, "student71b@example.com")

    assert api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).status_code == 201


def test_reported_payment_is_stored_with_student_source(setup):
    api, sessions, _, student, relationship_id, _ = setup
    report(api, student, relationship_id)
    with sessions() as db:
        payment = db.scalar(select(InformalPayment))
        assert payment.source == "STUDENT"
        assert payment.status == "PENDIENTE_CONFIRMACION"
