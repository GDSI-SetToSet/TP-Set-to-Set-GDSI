"""US-35: el entrenador da de baja a un alumno indicando el motivo."""

from datetime import date

import pytest
from sqlalchemy import func, select

from backend.src.models.informal_payment import InformalPayment
from backend.src.models.notification import Notification
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.tests.test_trainer_student_api import (
    create_relationship,
    register_and_login,
)

TODAY = "2026-11-17"


def termination_path(student_id: str) -> str:
    return f"/api/v1/trainers/me/students/{student_id}/termination"


@pytest.fixture
def setup(client, monkeypatch):
    monkeypatch.setattr(
        "backend.src.services.subscription_service.current_date",
        lambda: date.fromisoformat(TODAY),
    )
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    student = register_and_login(api, "alumna@example.com", "STUDENT")
    relationship_id, student_id = create_relationship(sessions, "coach@example.com", "alumna@example.com")
    with sessions() as db:
        profile = db.scalar(select(TrainerProfile).join(User).where(User.email == "coach@example.com"))
        profile.max_students = 5
        db.get(TrainingRelationship, relationship_id).start_date = date(2026, 11, 1)
        db.commit()
    return api, sessions, trainer, student, relationship_id, student_id


def terminate(api, headers, student_id, **body):
    return api.post(termination_path(student_id), params={"date": TODAY}, json=body, headers=headers)


# Escenarios 1 y 2 ------------------------------------------------------------------------


def test_termination_ends_relationship_with_reason(setup):
    api, sessions, trainer, _, relationship_id, student_id = setup

    response = terminate(api, trainer, student_id, category="falta_de_pago", detail="  Dos meses sin pagar  ")

    assert response.status_code == 200
    body = response.json()
    assert body["relationship_id"] == relationship_id
    assert body["status"] == "TERMINATED"
    assert body["end_date"] == TODAY
    assert body["category"] == "FALTA_DE_PAGO"
    assert body["detail"] == "Dos meses sin pagar"
    assert body["available_slots"] == 5
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        assert relationship.status == "TERMINATED"
        assert relationship.end_date == date(2026, 11, 17)
        assert relationship.terminated_at is not None
        assert relationship.termination_category == "FALTA_DE_PAGO"
        assert relationship.termination_reason == "Dos meses sin pagar"


def test_student_leaves_active_lists_and_frees_the_slot(setup):
    api, _, trainer, _, _, student_id = setup
    assert len(api.get("/api/v1/trainers/me/students", headers=trainer).json()) == 1
    assert len(api.get("/api/v1/trainers/me/subscriptions", headers=trainer).json()) == 1
    assert api.get("/api/v1/trainers/me/profile", headers=trainer).json()["available_slots"] == 4

    terminate(api, trainer, student_id, category="RAZONES_PERSONALES")

    assert api.get("/api/v1/trainers/me/students", headers=trainer).json() == []
    assert api.get("/api/v1/trainers/me/subscriptions", headers=trainer).json() == []
    assert api.get("/api/v1/trainers/me/profile", headers=trainer).json()["available_slots"] == 5


def test_termination_revokes_health_data_access(setup):
    api, _, trainer, _, _, student_id = setup
    questionnaire = f"/api/v1/students/{student_id}/health-questionnaire"
    assert api.get(questionnaire, headers=trainer).status_code != 403

    terminate(api, trainer, student_id, category="RAZONES_PERSONALES")

    assert api.get(questionnaire, headers=trainer).status_code == 403
    assert api.get(f"/api/v1/trainers/me/students/{student_id}", headers=trainer).status_code == 404


def test_chat_becomes_read_only_and_payments_are_kept(setup):
    api, sessions, trainer, student, relationship_id, student_id = setup
    messages = f"/api/v1/conversations/{relationship_id}/messages"
    api.post(messages, json={"body": "Hola"}, headers=trainer)
    api.post(
        f"/api/v1/trainers/me/students/{student_id}/payments",
        json={"paid_on": "2026-11-01", "amount": "12500", "method": "EFECTIVO", "months_covered": 1},
        headers=trainer,
    )

    terminate(api, trainer, student_id, category="OTRO", detail="Se mudó de ciudad")

    for headers in (trainer, student):
        assert api.post(messages, json={"body": "¿Seguimos?"}, headers=headers).status_code == 409
        assert [m["body"] for m in api.get(messages, headers=headers).json()["messages"]] == ["Hola"]
    with sessions() as db:
        assert db.scalar(select(func.count(InformalPayment.id))) == 1


def test_student_is_notified_with_the_reason(setup):
    api, sessions, trainer, _, relationship_id, student_id = setup

    terminate(api, trainer, student_id, category="OTRO", detail="Se mudó de ciudad")

    with sessions() as db:
        student_user_id = db.scalar(select(User.id).where(User.email == "alumna@example.com"))
        notification = db.scalar(
            select(Notification).where(
                Notification.recipient_id == student_user_id,
                Notification.type == "SUBSCRIPTION_TERMINATED",
            )
        )
    assert notification.title == "Tu entrenador Entrenador Principal finalizó tu suscripción"
    assert notification.message == "Motivo: Otro motivo. Se mudó de ciudad"
    assert notification.related_entity_id == relationship_id
    assert notification.is_read is False


def test_notification_without_detail_shows_only_the_category(setup):
    api, sessions, trainer, _, _, student_id = setup

    terminate(api, trainer, student_id, category="FALTA_DE_PAGO", detail="   ")

    with sessions() as db:
        message = db.scalar(select(Notification.message).where(Notification.type == "SUBSCRIPTION_TERMINATED"))
    assert message == "Motivo: Falta de pago."


# Escenario 3 -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ({}, "category", "Elegí el motivo de la baja."),
        ({"category": ""}, "category", "Elegí el motivo de la baja."),
        ({"category": "ME_CAYO_MAL"}, "category", "Elegí el motivo de la baja."),
        ({"category": "OTRO"}, "detail", "Contá el motivo de la baja (hasta 500 caracteres)."),
        ({"category": "OTRO", "detail": "   "}, "detail", "Contá el motivo de la baja (hasta 500 caracteres)."),
        ({"category": "FALTA_DE_PAGO", "detail": "x" * 501}, "detail", "Contá el motivo de la baja (hasta 500 caracteres)."),
    ],
)
def test_termination_requires_a_reason(setup, body, field, message):
    api, sessions, trainer, _, relationship_id, student_id = setup

    response = terminate(api, trainer, student_id, **body)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert {"field": field, "message": message} in response.json()["errors"]
    with sessions() as db:
        assert db.get(TrainingRelationship, relationship_id).status == "ACTIVE"


# Autorización ----------------------------------------------------------------------------


def test_repeated_termination_and_foreign_trainer_get_not_found(setup):
    api, _, trainer, _, _, student_id = setup
    other = register_and_login(api, "otro@example.com", "TRAINER")

    assert terminate(api, other, student_id, category="OTRO", detail="x").status_code == 404
    assert terminate(api, trainer, student_id, category="RAZONES_PERSONALES").status_code == 200
    assert terminate(api, trainer, student_id, category="RAZONES_PERSONALES").status_code == 404


def test_students_and_anonymous_users_cannot_terminate(setup):
    api, _, _, student, _, student_id = setup
    assert terminate(api, student, student_id, category="RAZONES_PERSONALES").status_code == 403
    assert api.post(termination_path(student_id), json={"category": "OTRO"}).status_code == 401
