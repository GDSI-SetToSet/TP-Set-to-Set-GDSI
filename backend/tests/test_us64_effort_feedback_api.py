"""US-64: devolución del entrenador sobre el esfuerzo reportado."""

from sqlalchemy import select

from backend.src.models.effort_feedback import EffortFeedback
from backend.src.models.notification import Notification
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.tests.test_us60_rpe_api import (
    ASSIGNED_PATH,
    TEMPLATES_PATH,
    register_and_login,
    setup_routine_and_assignment,
)


def setup_pair(api, sessions, suffix: str):
    trainer_email = f"trainer_us64_{suffix}@example.com"
    student_email = f"student_us64_{suffix}@example.com"
    trainer = register_and_login(api, trainer_email, "TRAINER")
    student = register_and_login(api, student_email, "STUDENT")
    _, rel_id, _ = setup_routine_and_assignment(api, sessions, trainer, student_email, trainer_email)
    return trainer, student, rel_id, student_email


def finished_session(api, student, rpe: int | None = 8) -> str:
    session_id = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()["id"]
    payload = {"rpe": rpe} if rpe is not None else {}
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{session_id}/finish", headers=student, json=payload).status_code == 200
    return session_id


def feedback_url(rel_id: str, session_id: str) -> str:
    return f"{TEMPLATES_PATH}/assignments/{rel_id}/workout-sessions/{session_id}/effort-feedback"


def student_notifications(sessions, email: str) -> list[Notification]:
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == email))
        return list(
            db.scalars(
                select(Notification)
                .where(Notification.recipient_id == user.id, Notification.type == "EFFORT_FEEDBACK")
                .order_by(Notification.created_at)
            )
        )


def test_trainer_leaves_feedback_and_student_is_notified(client):
    api, sessions = client
    trainer, student, rel_id, student_email = setup_pair(api, sessions, "create")
    session_id = finished_session(api, student, rpe=6)

    response = api.put(
        feedback_url(rel_id, session_id),
        headers=trainer,
        json={"category": "MORE_EFFORT", "comment": "  Podés subir 2,5 kg en press.  "},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["category"] == "MORE_EFFORT"
    assert data["comment"] == "Podés subir 2,5 kg en press."
    assert data["rpe"] == 6
    assert data["day_name"] == "Día 1"
    assert data["seen_at"] is None
    notifications = student_notifications(sessions, student_email)
    assert len(notifications) == 1
    assert notifications[0].title == "Tenés una devolución de tu entrenador"
    assert "Podrías exigir más" in notifications[0].message
    assert notifications[0].related_entity_id == data["id"]


def test_editing_replaces_feedback_resets_seen_and_notifies_again(client):
    api, sessions = client
    trainer, student, rel_id, student_email = setup_pair(api, sessions, "edit")
    session_id = finished_session(api, student)
    first = api.put(feedback_url(rel_id, session_id), headers=trainer, json={"category": "ADEQUATE"}).json()
    assert api.post(f"{ASSIGNED_PATH}/effort-feedback/{first['id']}/seen", headers=student).status_code == 200

    second = api.put(
        feedback_url(rel_id, session_id),
        headers=trainer,
        json={"category": "LESS_INTENSITY", "comment": ""},
    )

    assert second.status_code == 200
    data = second.json()
    assert data["id"] == first["id"]
    assert data["category"] == "LESS_INTENSITY"
    assert data["comment"] is None
    assert data["seen_at"] is None
    with sessions() as db:
        assert len(db.scalars(select(EffortFeedback)).all()) == 1
    notifications = student_notifications(sessions, student_email)
    assert [n.title for n in notifications] == [
        "Tenés una devolución de tu entrenador",
        "Tu entrenador actualizó su devolución",
    ]


def test_feedback_requires_reported_rpe(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "norpe")
    session_id = finished_session(api, student, rpe=None)

    response = api.put(feedback_url(rel_id, session_id), headers=trainer, json={"category": "ADEQUATE"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "esfuerzo reportado" in response.json()["detail"]


def test_feedback_requires_finished_session(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "active")
    session_id = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()["id"]

    assert api.put(feedback_url(rel_id, session_id), headers=trainer, json={"category": "ADEQUATE"}).status_code == 422


def test_feedback_validates_category_and_comment_length(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "invalid")
    session_id = finished_session(api, student)

    missing = api.put(feedback_url(rel_id, session_id), headers=trainer, json={})
    invalid = api.put(feedback_url(rel_id, session_id), headers=trainer, json={"category": "OTRA"})
    too_long = api.put(
        feedback_url(rel_id, session_id),
        headers=trainer,
        json={"category": "ADEQUATE", "comment": "x" * 501},
    )
    max_length = api.put(
        feedback_url(rel_id, session_id),
        headers=trainer,
        json={"category": "ADEQUATE", "comment": "x" * 500},
    )

    assert missing.status_code == 422
    assert invalid.status_code == 422
    assert any(error["field"].endswith("category") for error in invalid.json()["errors"])
    assert too_long.status_code == 422
    assert any(error["field"].endswith("comment") for error in too_long.json()["errors"])
    assert max_length.status_code == 200


def test_feedback_rejects_other_trainer_and_foreign_session(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "owner")
    other_trainer, other_student, other_rel_id, _ = setup_pair(api, sessions, "other")
    session_id = finished_session(api, student)
    other_session_id = finished_session(api, other_student)

    assert api.put(feedback_url(rel_id, session_id), headers=other_trainer, json={"category": "ADEQUATE"}).status_code == 404
    assert api.put(feedback_url(rel_id, other_session_id), headers=trainer, json={"category": "ADEQUATE"}).status_code == 404
    assert api.put(feedback_url(other_rel_id, "no-existe"), headers=other_trainer, json={"category": "ADEQUATE"}).status_code == 404
    assert api.put(feedback_url(rel_id, session_id), headers=student, json={"category": "ADEQUATE"}).status_code == 403


def test_feedback_rejected_when_relationship_is_not_active(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "inactive")
    session_id = finished_session(api, student)
    created = api.put(feedback_url(rel_id, session_id), headers=trainer, json={"category": "ADEQUATE"})
    assert created.status_code == 200
    with sessions() as db:
        db.get(TrainingRelationship, rel_id).status = "ENDED"
        db.commit()

    assert api.put(feedback_url(rel_id, session_id), headers=trainer, json={"category": "ADEQUATE"}).status_code == 404
    assert api.get(f"{ASSIGNED_PATH}/effort-feedback", headers=student).json() == []


def test_student_history_is_empty_without_feedback(client):
    api, sessions = client
    _, student, _, _ = setup_pair(api, sessions, "empty")

    response = api.get(f"{ASSIGNED_PATH}/effort-feedback", headers=student)

    assert response.status_code == 200
    assert response.json() == []


def test_student_history_lists_most_recent_first_and_marks_seen(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "history")
    first_session = finished_session(api, student, rpe=5)
    second_session = finished_session(api, student, rpe=9)
    api.put(feedback_url(rel_id, first_session), headers=trainer, json={"category": "MORE_EFFORT"})
    api.put(feedback_url(rel_id, second_session), headers=trainer, json={"category": "LESS_INTENSITY"})

    history = api.get(f"{ASSIGNED_PATH}/effort-feedback", headers=student).json()

    assert [item["session_id"] for item in history] == [second_session, first_session]
    assert all(item["seen_at"] is None for item in history)

    seen = api.post(f"{ASSIGNED_PATH}/effort-feedback/{history[0]['id']}/seen", headers=student)
    again = api.post(f"{ASSIGNED_PATH}/effort-feedback/{history[0]['id']}/seen", headers=student)

    assert seen.status_code == 200
    assert seen.json()["seen_at"] is not None
    assert again.json()["seen_at"] == seen.json()["seen_at"]
    refreshed = api.get(f"{ASSIGNED_PATH}/effort-feedback", headers=student).json()
    assert refreshed[0]["seen_at"] is not None
    assert refreshed[1]["seen_at"] is None


def test_student_cannot_mark_feedback_of_another_student(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "mine")
    _, intruder, _, _ = setup_pair(api, sessions, "intruder")
    session_id = finished_session(api, student)
    feedback_id = api.put(feedback_url(rel_id, session_id), headers=trainer, json={"category": "ADEQUATE"}).json()["id"]

    assert api.post(f"{ASSIGNED_PATH}/effort-feedback/{feedback_id}/seen", headers=intruder).status_code == 404
    assert api.get(f"{ASSIGNED_PATH}/effort-feedback", headers=intruder).json() == []
    assert api.get(f"{ASSIGNED_PATH}/effort-feedback", headers=trainer).status_code == 403


def test_sessions_include_effort_feedback_for_trainer_and_student(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "sessions")
    with_feedback = finished_session(api, student)
    without_feedback = finished_session(api, student)
    api.put(feedback_url(rel_id, with_feedback), headers=trainer, json={"category": "ADEQUATE", "comment": "Bien"})

    trainer_sessions = api.get(f"{TEMPLATES_PATH}/assignments/{rel_id}/workout-sessions", headers=trainer).json()
    student_sessions = api.get(f"{ASSIGNED_PATH}/workout-sessions", headers=student).json()

    for listing in (trainer_sessions, student_sessions):
        by_id = {item["id"]: item for item in listing}
        assert by_id[with_feedback]["effort_feedback"]["comment"] == "Bien"
        assert by_id[without_feedback]["effort_feedback"] is None


def test_trainer_session_attention_state_clears_after_feedback_is_saved(client):
    api, sessions = client
    trainer, student, rel_id, _ = setup_pair(api, sessions, "attention")
    pending_session = finished_session(api, student, rpe=8)
    no_rpe_session = finished_session(api, student, rpe=None)

    before = api.get(
        f"{TEMPLATES_PATH}/assignments/{rel_id}/workout-sessions",
        headers=trainer,
    )
    assert before.status_code == 200
    before_by_id = {item["id"]: item for item in before.json()}
    pending = [
        item for item in before.json()
        if item["rpe"] is not None and item["effort_feedback"] is None
    ]
    assert len(pending) == 1
    assert pending[0]["id"] == pending_session
    assert before_by_id[no_rpe_session]["rpe"] is None

    saved = api.put(
        feedback_url(rel_id, pending_session),
        headers=trainer,
        json={"category": "ADEQUATE"},
    )
    assert saved.status_code == 200

    after = api.get(
        f"{TEMPLATES_PATH}/assignments/{rel_id}/workout-sessions",
        headers=trainer,
    )
    assert after.status_code == 200
    after_by_id = {item["id"]: item for item in after.json()}
    pending_after = [
        item for item in after.json()
        if item["rpe"] is not None and item["effort_feedback"] is None
    ]
    assert pending_after == []
    assert after_by_id[pending_session]["effort_feedback"]["category"] == "ADEQUATE"
