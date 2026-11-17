"""US-21: canal de mensajes entrenador–alumno (una conversación por vínculo)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.src.models.notification import Notification
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.tests.test_trainer_student_api import (
    create_relationship,
    register_and_login,
)

CONVERSATIONS = "/api/v1/conversations"


def messages_path(relationship_id: str) -> str:
    return f"{CONVERSATIONS}/{relationship_id}/messages"


def read_path(relationship_id: str) -> str:
    return f"{CONVERSATIONS}/{relationship_id}/read"


@pytest.fixture
def pair(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    student = register_and_login(api, "alumna@example.com", "STUDENT")
    relationship_id, student_id = create_relationship(sessions, "coach@example.com", "alumna@example.com")
    return api, sessions, trainer, student, relationship_id, student_id


def send(api, headers, relationship_id, body):
    return api.post(messages_path(relationship_id), json={"body": body}, headers=headers)


def user_id(sessions, email: str) -> str:
    with sessions() as db:
        return db.scalar(select(User.id).where(User.email == email))


def unread_message_notifications(sessions, email: str) -> list[Notification]:
    with sessions() as db:
        return list(
            db.scalars(
                select(Notification).where(
                    Notification.recipient_id == user_id(sessions, email),
                    Notification.type == "NEW_MESSAGE",
                    Notification.is_read.is_(False),
                )
            )
        )


# Escenario 1 -----------------------------------------------------------------------------


def test_both_parties_open_the_same_conversation(pair):
    api, _, trainer, student, relationship_id, student_id = pair

    trainer_list = api.get(CONVERSATIONS, headers=trainer).json()
    student_list = api.get(CONVERSATIONS, headers=student).json()

    assert [c["relationship_id"] for c in trainer_list] == [relationship_id]
    assert [c["relationship_id"] for c in student_list] == [relationship_id]
    assert trainer_list[0]["counterpart_name"] == "Valeria Alumna"
    assert trainer_list[0]["counterpart_role"] == "STUDENT"
    assert trainer_list[0]["student_id"] == student_id
    assert student_list[0]["counterpart_name"] == "Entrenador Principal"
    assert student_list[0]["counterpart_role"] == "TRAINER"
    assert student_list[0]["can_send"] is True
    assert student_list[0]["last_message"] is None
    assert student_list[0]["plan_title"] == "Plan Premium"

    detail = api.get(messages_path(relationship_id), headers=student)
    assert detail.status_code == 200
    assert detail.json()["messages"] == []


def test_student_with_two_trainers_has_two_conversations(pair):
    api, sessions, _, student, _, student_id = pair
    register_and_login(api, "coach2@example.com", "TRAINER")
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        coach2 = db.scalar(select(User).where(User.email == "coach2@example.com"))
        trainer2 = TrainerProfile(user_id=coach2.id, full_name="Segundo Coach", status="PUBLISHED", created_at=now, updated_at=now)
        db.add(trainer2)
        db.flush()
        plan = TrainingPlan(trainer_id=trainer2.id, title="Running", monthly_price=Decimal(9000), currency="ARS",
                            is_active=True, created_at=now, updated_at=now)
        db.add(plan)
        db.flush()
        db.add(TrainingRelationship(trainer_id=trainer2.id, student_id=student_id, plan_id=plan.id,
                                    agreed_monthly_price=Decimal(9000), agreed_currency="ARS",
                                    status="ACTIVE", start_date=now.date()))
        db.commit()

    names = {c["counterpart_name"] for c in api.get(CONVERSATIONS, headers=student).json()}

    assert names == {"Entrenador Principal", "Segundo Coach"}


# Escenarios 2 y 3 ------------------------------------------------------------------------


def test_messages_are_stored_in_order_and_visible_to_both(pair):
    api, _, trainer, student, relationship_id, _ = pair

    first = send(api, trainer, relationship_id, "  Hola Valeria, ¿cómo estás?  ")
    send(api, student, relationship_id, "¡Bien! ¿Cambiamos el turno del jueves?")
    send(api, trainer, relationship_id, "Dale, pasamos al viernes.")

    assert first.status_code == 201
    assert first.json()["body"] == "Hola Valeria, ¿cómo estás?"
    assert first.json()["is_mine"] is True
    assert first.json()["sender_role"] == "TRAINER"
    assert first.json()["kind"] == "TEXT"
    for headers, mine in ((trainer, [True, False, True]), (student, [False, True, False])):
        messages = api.get(messages_path(relationship_id), headers=headers).json()["messages"]
        assert [m["body"] for m in messages] == [
            "Hola Valeria, ¿cómo estás?",
            "¡Bien! ¿Cambiamos el turno del jueves?",
            "Dale, pasamos al viernes.",
        ]
        assert [m["is_mine"] for m in messages] == mine
    summary = api.get(CONVERSATIONS, headers=student).json()[0]
    assert summary["last_message"]["body"] == "Dale, pasamos al viernes."
    assert summary["last_message"]["is_mine"] is False


def test_notification_is_grouped_per_conversation_and_cleared_on_read(pair):
    api, sessions, trainer, student, relationship_id, _ = pair

    for body in ("Uno", "Dos", "Tres"):
        send(api, trainer, relationship_id, body)

    notifications = unread_message_notifications(sessions, "alumna@example.com")
    assert len(notifications) == 1
    assert notifications[0].title == "3 mensajes nuevos de Entrenador Principal"
    assert notifications[0].message == "Tres"
    assert notifications[0].related_entity_id == relationship_id
    assert api.get(CONVERSATIONS, headers=student).json()[0]["unread_count"] == 3

    assert api.post(read_path(relationship_id), headers=student).status_code == 204

    assert unread_message_notifications(sessions, "alumna@example.com") == []
    assert api.get(CONVERSATIONS, headers=student).json()[0]["unread_count"] == 0
    messages = api.get(messages_path(relationship_id), headers=trainer).json()["messages"]
    assert all(m["read_at"] is not None for m in messages)

    send(api, trainer, relationship_id, "Cuatro")
    notifications = unread_message_notifications(sessions, "alumna@example.com")
    assert len(notifications) == 1
    assert notifications[0].title == "Nuevo mensaje de Entrenador Principal"


def test_reading_does_not_mark_own_messages(pair):
    api, _, trainer, _, relationship_id, _ = pair
    send(api, trainer, relationship_id, "Hola")

    api.post(read_path(relationship_id), headers=trainer)

    assert api.get(messages_path(relationship_id), headers=trainer).json()["messages"][0]["read_at"] is None


# Escenario 4 -----------------------------------------------------------------------------


def test_terminated_relationship_blocks_sending_but_keeps_history(pair):
    api, sessions, trainer, student, relationship_id, _ = pair
    send(api, student, relationship_id, "Gracias por todo")
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()

    for headers in (student, trainer):
        response = send(api, headers, relationship_id, "¿Seguimos?")
        assert response.status_code == 409
        assert response.headers["content-type"].startswith("application/problem+json")
        assert "no está activo" in response.json()["detail"]
        history = api.get(messages_path(relationship_id), headers=headers)
        assert history.status_code == 200
        assert [m["body"] for m in history.json()["messages"]] == ["Gracias por todo"]
    summary = api.get(CONVERSATIONS, headers=student).json()[0]
    assert summary["status"] == "TERMINATED"
    assert summary["can_send"] is False


def test_terminated_relationship_without_messages_is_not_listed(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    register_and_login(api, "ex@example.com", "STUDENT")
    create_relationship(sessions, "coach@example.com", "ex@example.com", status="TERMINATED")

    assert api.get(CONVERSATIONS, headers=trainer).json() == []


# Validación y autorización ---------------------------------------------------------------


@pytest.mark.parametrize("body", [{}, {"body": ""}, {"body": "   "}, {"body": "x" * 2001}, {"body": 5}])
def test_message_body_is_validated(pair, body):
    api, _, trainer, _, relationship_id, _ = pair

    response = api.post(messages_path(relationship_id), json=body, headers=trainer)

    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "body", "message": "Escribí un mensaje (hasta 2000 caracteres)."}
    ]


def test_message_of_2000_characters_is_accepted(pair):
    api, _, trainer, _, relationship_id, _ = pair
    assert send(api, trainer, relationship_id, "x" * 2000).status_code == 201


def test_third_parties_get_not_found(pair):
    api, _, _, _, relationship_id, _ = pair
    intruder_trainer = register_and_login(api, "otro@example.com", "TRAINER")
    intruder_student = register_and_login(api, "otra@example.com", "STUDENT")

    for headers in (intruder_trainer, intruder_student):
        assert api.get(messages_path(relationship_id), headers=headers).status_code == 404
        assert send(api, headers, relationship_id, "Hola").status_code == 404
        assert api.post(read_path(relationship_id), headers=headers).status_code == 404
    assert api.get(messages_path("no-existe"), headers=intruder_trainer).status_code == 404


def test_requires_authentication(pair):
    api, _, _, _, relationship_id, _ = pair
    assert api.get(CONVERSATIONS).status_code == 401
    assert api.post(messages_path(relationship_id), json={"body": "Hola"}).status_code == 401


def test_user_without_profile_has_no_conversations(client):
    api, _ = client
    headers = register_and_login(api, "nuevo@example.com", "STUDENT")
    assert api.get(CONVERSATIONS, headers=headers).json() == []


def test_plain_message_cannot_be_pinned(pair):
    api, _, trainer, _, relationship_id, _ = pair

    response = api.post(
        messages_path(relationship_id), json={"body": "Hola", "pin_as_technical_note": True}, headers=trainer
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "pin_as_technical_note"


def test_student_profile_names_fall_back_to_email(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    register_and_login(api, "sinnombre@example.com", "STUDENT")
    relationship_id, student_id = create_relationship(sessions, "coach@example.com", "sinnombre@example.com")
    with sessions() as db:
        profile = db.get(StudentProfile, student_id)
        profile.first_name = None
        profile.last_name = None
        db.commit()

    assert api.get(CONVERSATIONS, headers=trainer).json()[0]["counterpart_name"] == "sinnombre@example.com"
    assert send(api, trainer, relationship_id, "Hola").status_code == 201
