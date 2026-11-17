"""US-62: consultas técnicas sobre un ejercicio, bandeja del entrenador y notas técnicas fijadas."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from backend.src.models.exercise import Exercise
from backend.src.models.notification import Notification
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.tests.test_trainer_student_api import (
    create_relationship,
    register_and_login,
)

INBOX = "/api/v1/trainers/me/technical-queries"
NOTES = "/api/v1/students/me/technical-notes"


def queries_path(relationship_id: str) -> str:
    return f"/api/v1/conversations/{relationship_id}/technical-queries"


def messages_path(relationship_id: str) -> str:
    return f"/api/v1/conversations/{relationship_id}/messages"


def exercise_history_path(relationship_id: str, exercise_id: str) -> str:
    return f"/api/v1/conversations/{relationship_id}/exercises/{exercise_id}/technical-queries"


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def add_exercise(sessions, relationship_id: str, name: str = "Sentadilla") -> str:
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        exercise = Exercise(
            trainer_id=relationship.trainer_id,
            name=name,
            description="Ejercicio de prueba",
            category="STRENGTH",
            target_muscle_group="Piernas",
            equipment_needed="Barra",
            contraindicated_zones=[],
            created_at=now(),
            updated_at=now(),
        )
        db.add(exercise)
        db.commit()
        return exercise.id


def add_session(sessions, relationship_id: str) -> str:
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        session = WorkoutSession(
            student_id=relationship.student_id,
            relationship_id=relationship.id,
            routine_id="rutina",
            day_name="Día 1",
            modality="GYM",
            started_at=now(),
        )
        db.add(session)
        db.commit()
        return session.id


@pytest.fixture
def setup(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    student = register_and_login(api, "alumna@example.com", "STUDENT")
    relationship_id, student_id = create_relationship(sessions, "coach@example.com", "alumna@example.com")
    exercise_id = add_exercise(sessions, relationship_id)
    return api, sessions, trainer, student, relationship_id, student_id, exercise_id


def ask(api, headers, relationship_id, exercise_id, body="¿Bajo hasta el paralelo o más?", **extra):
    return api.post(
        queries_path(relationship_id), json={"exercise_id": exercise_id, "body": body, **extra}, headers=headers
    )


def reply(api, headers, relationship_id, query_id, body="Hasta el paralelo, espalda neutra.", pin=False):
    return api.post(
        messages_path(relationship_id),
        json={"body": body, "reply_to_message_id": query_id, "pin_as_technical_note": pin},
        headers=headers,
    )


# Escenario 1 -----------------------------------------------------------------------------


def test_student_asks_about_an_exercise_from_a_session(setup):
    api, sessions, _, student, relationship_id, _, exercise_id = setup
    session_id = add_session(sessions, relationship_id)

    response = ask(api, student, relationship_id, exercise_id, session_id=session_id, set_number=3)

    assert response.status_code == 201
    query = response.json()
    assert query["kind"] == "TECHNICAL_QUERY"
    assert query["exercise"] == {"id": exercise_id, "name": "Sentadilla"}
    assert query["session_id"] == session_id
    assert query["set_number"] == 3
    assert query["is_answered"] is False
    chat = api.get(messages_path(relationship_id), headers=student).json()["messages"]
    assert [m["id"] for m in chat] == [query["id"]]


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"body": "Hola"}, "exercise_id"),
        ({"exercise_id": "x", "body": "  "}, "body"),
        ({"exercise_id": "x", "body": "Hola", "set_number": 0}, "set_number"),
        ({"exercise_id": "x", "body": "Hola", "set_number": 51}, "set_number"),
        ({"exercise_id": "x", "body": "Hola", "set_number": "3"}, "set_number"),
    ],
)
def test_query_payload_is_validated(setup, payload, field):
    api, _, _, student, relationship_id, _, _ = setup

    response = api.post(queries_path(relationship_id), json=payload, headers=student)

    assert response.status_code == 422
    assert field in {error["field"] for error in response.json()["errors"]}


def test_query_requires_an_exercise_of_the_trainer_and_an_own_session(setup):
    api, sessions, _, student, relationship_id, _, exercise_id = setup
    register_and_login(api, "otro@example.com", "TRAINER")
    register_and_login(api, "otra@example.com", "STUDENT")
    other_relationship, _ = create_relationship(sessions, "otro@example.com", "otra@example.com")
    foreign_exercise = add_exercise(sessions, other_relationship, "Remo")
    foreign_session = add_session(sessions, other_relationship)
    with sessions() as db:
        deleted = db.get(Exercise, add_exercise(sessions, relationship_id, "Borrado"))
        deleted.deleted_at = now()
        db.commit()
        deleted_id = deleted.id

    for bad_exercise in ("no-existe", foreign_exercise, deleted_id):
        response = ask(api, student, relationship_id, bad_exercise)
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "exercise_id"
    response = ask(api, student, relationship_id, exercise_id, session_id=foreign_session)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "session_id"


def test_trainer_cannot_create_queries(setup):
    api, _, trainer, _, relationship_id, _, exercise_id = setup
    assert ask(api, trainer, relationship_id, exercise_id).status_code == 403


def test_terminated_relationship_blocks_queries(setup):
    api, sessions, _, student, relationship_id, _, exercise_id = setup
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()
    assert ask(api, student, relationship_id, exercise_id).status_code == 409


# Escenario 2 -----------------------------------------------------------------------------


def test_trainer_is_notified_and_sees_pending_queries_grouped_by_student(setup):
    api, sessions, trainer, student, relationship_id, student_id, exercise_id = setup
    first = ask(api, student, relationship_id, exercise_id, body="Primera").json()
    second = ask(api, student, relationship_id, exercise_id, body="Segunda").json()
    register_and_login(api, "beto@example.com", "STUDENT")
    other_relationship, other_student = create_relationship(sessions, "coach@example.com", "beto@example.com")
    other_exercise = add_exercise(sessions, other_relationship, "Press")
    beto = api.post("/api/v1/auth/login", json={"email": "beto@example.com", "password": "StrongPass123"})
    beto_headers = {"Authorization": f"Bearer {beto.json()['access_token']}"}
    ask(api, beto_headers, other_relationship, other_exercise, body="De Beto")

    with sessions() as db:
        coach_id = db.scalar(select(User.id).where(User.email == "coach@example.com"))
        notifications = list(
            db.scalars(
                select(Notification).where(
                    Notification.recipient_id == coach_id, Notification.type == "TECHNICAL_QUERY"
                )
            )
        )
    assert len(notifications) == 3
    assert notifications[0].title == "Consulta técnica de Valeria Alumna"
    assert notifications[0].message == "Sentadilla: Primera"
    assert notifications[0].related_entity_id == first["id"]
    assert notifications[0].related_student_id == student_id

    inbox = api.get(INBOX, headers=trainer).json()
    assert [group["student_id"] for group in inbox] == [student_id, other_student]
    assert [q["body"] for q in inbox[0]["queries"]] == ["Primera", "Segunda"]
    assert inbox[0]["student_name"] == "Valeria Alumna"
    assert inbox[0]["relationship_id"] == relationship_id

    assert reply(api, trainer, relationship_id, first["id"]).status_code == 201
    inbox = api.get(INBOX, headers=trainer).json()
    assert [q["id"] for q in inbox[0]["queries"]] == [second["id"]]
    chat = api.get(messages_path(relationship_id), headers=student).json()["messages"]
    assert next(m for m in chat if m["id"] == first["id"])["is_answered"] is True


def test_inbox_is_only_for_trainers_and_excludes_terminated(setup):
    api, sessions, trainer, student, relationship_id, _, exercise_id = setup
    ask(api, student, relationship_id, exercise_id)
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()

    assert api.get(INBOX, headers=student).status_code == 403
    assert api.get(INBOX, headers=trainer).json() == []


def test_only_the_trainer_replies_and_only_to_queries_of_the_conversation(setup):
    api, _, trainer, student, relationship_id, _, exercise_id = setup
    query = ask(api, student, relationship_id, exercise_id).json()
    text = api.post(messages_path(relationship_id), json={"body": "Hola"}, headers=trainer).json()

    assert reply(api, student, relationship_id, query["id"]).status_code == 403
    for target in (text["id"], "no-existe"):
        response = reply(api, trainer, relationship_id, target)
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "reply_to_message_id"


# Escenario 3 -----------------------------------------------------------------------------


def test_pinned_reply_becomes_a_note_until_acknowledged(setup):
    api, sessions, trainer, student, relationship_id, _, exercise_id = setup
    query = ask(api, student, relationship_id, exercise_id).json()

    answer = reply(api, trainer, relationship_id, query["id"], body="Rodillas hacia afuera.", pin=True)

    assert answer.status_code == 201
    assert answer.json()["technical_note"]["acknowledged_at"] is None
    notes = api.get(NOTES, headers=student).json()
    assert len(notes) == 1
    assert notes[0]["exercise_id"] == exercise_id
    assert notes[0]["exercise_name"] == "Sentadilla"
    assert notes[0]["body"] == "Rodillas hacia afuera."
    assert notes[0]["trainer_name"] == "Entrenador Principal"

    session_id = add_session(sessions, relationship_id)
    ack = api.post(f"{NOTES}/{notes[0]['id']}/acknowledge", json={"session_id": session_id}, headers=student)
    assert ack.status_code == 200
    assert ack.json()["acknowledged_at"] is not None
    assert api.get(NOTES, headers=student).json() == []
    again = api.post(f"{NOTES}/{notes[0]['id']}/acknowledge", headers=student)
    assert again.status_code == 200
    assert again.json()["acknowledged_at"] == ack.json()["acknowledged_at"]


def test_unpinned_reply_creates_no_note(setup):
    api, _, trainer, student, relationship_id, _, exercise_id = setup
    query = ask(api, student, relationship_id, exercise_id).json()

    answer = reply(api, trainer, relationship_id, query["id"])

    assert answer.json()["technical_note"] is None
    assert api.get(NOTES, headers=student).json() == []


def test_notes_are_private_to_the_student(setup):
    api, _, trainer, student, relationship_id, _, exercise_id = setup
    query = ask(api, student, relationship_id, exercise_id).json()
    reply(api, trainer, relationship_id, query["id"], pin=True)
    note_id = api.get(NOTES, headers=student).json()[0]["id"]
    other = register_and_login(api, "otra@example.com", "STUDENT")

    assert api.get(NOTES, headers=trainer).status_code == 403
    assert api.post(f"{NOTES}/{note_id}/acknowledge", headers=trainer).status_code == 403
    assert api.post(f"{NOTES}/{note_id}/acknowledge", headers=other).status_code == 404
    assert api.post(f"{NOTES}/no-existe/acknowledge", headers=student).status_code == 404
    assert api.get(NOTES, headers=other).json() == []


# Escenario 4 -----------------------------------------------------------------------------


def test_exercise_history_shows_queries_with_their_replies_for_both(setup):
    api, sessions, trainer, student, relationship_id, _, exercise_id = setup
    other_exercise = add_exercise(sessions, relationship_id, "Peso muerto")
    first = ask(api, student, relationship_id, exercise_id, body="Primera").json()
    ask(api, student, relationship_id, other_exercise, body="Otra")
    second = ask(api, student, relationship_id, exercise_id, body="Segunda").json()
    reply(api, trainer, relationship_id, first["id"], body="Respuesta 1", pin=True)
    reply(api, trainer, relationship_id, first["id"], body="Respuesta 1 bis")

    for headers in (student, trainer):
        threads = api.get(exercise_history_path(relationship_id, exercise_id), headers=headers)
        assert threads.status_code == 200
        body = threads.json()
        assert [t["query"]["id"] for t in body] == [first["id"], second["id"]]
        assert [r["body"] for r in body[0]["replies"]] == ["Respuesta 1", "Respuesta 1 bis"]
        assert body[0]["replies"][0]["technical_note"] is not None
        assert body[1]["replies"] == []
    assert api.get(exercise_history_path(relationship_id, "sin-consultas"), headers=student).json() == []


def test_exercise_history_is_private_to_the_relationship(setup):
    api, _, _, _, relationship_id, _, exercise_id = setup
    intruder = register_and_login(api, "otra@example.com", "STUDENT")
    assert api.get(exercise_history_path(relationship_id, exercise_id), headers=intruder).status_code == 404
