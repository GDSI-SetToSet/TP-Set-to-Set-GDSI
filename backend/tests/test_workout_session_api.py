from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.services import routine_template_service

TEMPLATES_PATH = "/api/v1/routine-templates"
ASSIGNED_PATH = "/api/v1/students/me/routine-templates/assigned"


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    registration = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "role": role},
    )
    assert registration.status_code == 201
    response = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_assigned_routine(api, sessions, trainer, student_email: str) -> tuple[str, str]:
    exercise_response = api.post(
        "/api/v1/exercises",
        headers=trainer,
        json={
            "name": "Sentadilla",
            "description": "Flexión de piernas",
            "category": "FUERZA",
            "target_muscle_group": "Piernas",
            "equipment_needed": "Mancuerna",
        },
    )
    assert exercise_response.status_code == 201
    exercise_id = exercise_response.json()["id"]
    routine_response = api.post(
        TEMPLATES_PATH,
        headers=trainer,
        json={
            "name": "Rutina de prueba",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": "Día 1",
                    "blocks": [
                        {
                            "name": "Principal",
                            "exercises": [
                                {
                                    "exercise_id": exercise_id,
                                    "sets": 3,
                                    "reps": "8",
                                    "rest_seconds": 60,
                                    "target_weight_kg": 10,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert routine_response.status_code == 201
    routine_id = routine_response.json()["id"]
    relationship_id = link_student(sessions, "trainer@example.com", student_email)
    assigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{relationship_id}",
        headers=trainer,
        json={"routine_template_id": routine_id},
    )
    assert assigned.status_code == 200
    return exercise_id, relationship_id


def link_student(sessions, trainer_email: str, student_email: str) -> str:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))
        profile = StudentProfile(user_id=student_user.id, status="PUBLISHED", created_at=now, updated_at=now)
        plan = TrainingPlan(
            trainer_id=trainer_user.trainer_profile.id,
            title="Plan de prueba",
            monthly_price=Decimal("25000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add_all([profile, plan])
        db.flush()
        relationship = TrainingRelationship(
            student_id=profile.id,
            trainer_id=trainer_user.trainer_profile.id,
            plan_id=plan.id,
            agreed_monthly_price=Decimal("25000.00"),
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=now.date(),
        )
        db.add(relationship)
        db.flush()
        relationship_id = relationship.id
        db.commit()
        return relationship_id


def parse_api_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def test_workout_session_records_start_finish_total_time_and_set_duration(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, relationship_id = create_assigned_routine(api, sessions, trainer, "student@example.com")
    sessions_path = f"{ASSIGNED_PATH}/workout-sessions"
    logs_path = f"{ASSIGNED_PATH}/workout-logs"

    clock = {"now": datetime(2026, 11, 9, 12, 0, tzinfo=UTC)}
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: clock["now"])
    started = api.post(sessions_path, headers=student, json={"day_name": "Día 1"})

    assert started.status_code == 201
    started_session = started.json()
    assert started_session["finished_at"] is None
    assert parse_api_datetime(started_session["started_at"]) == clock["now"]
    assert api.get(sessions_path, headers=student).json() == []

    missing_weight = api.post(
        logs_path,
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "session_id": started_session["id"],
        },
    )
    assert missing_weight.status_code == 422
    missing_reps = api.post(
        logs_path,
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "weight_kg": 10,
            "session_id": started_session["id"],
        },
    )
    assert missing_reps.status_code == 422

    recorded = api.post(
        logs_path,
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 10,
            "duration_seconds": 37,
            "session_id": started_session["id"],
        },
    )
    assert recorded.status_code == 201
    assert recorded.json()["session_id"] == started_session["id"]
    assert recorded.json()["duration_seconds"] == 37
    trainer_logs = api.get(
        f"{TEMPLATES_PATH}/assignments/{relationship_id}/workout-logs",
        headers=trainer,
    )
    assert trainer_logs.status_code == 200
    assert [log["id"] for log in trainer_logs.json()] == [recorded.json()["id"]]
    other_trainer = register_and_login(api, "other-trainer@example.com", "TRAINER")
    assert api.get(
        f"{TEMPLATES_PATH}/assignments/{relationship_id}/workout-logs",
        headers=other_trainer,
    ).status_code == 404

    wrong_day = api.post(
        logs_path,
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 2",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 10,
            "duration_seconds": 37,
            "session_id": started_session["id"],
        },
    )
    assert wrong_day.status_code == 422

    clock["now"] += timedelta(minutes=42, seconds=15)
    finished = api.post(f"{sessions_path}/{started_session['id']}/finish", headers=student)
    assert finished.status_code == 200
    assert parse_api_datetime(finished.json()["finished_at"]) == clock["now"]
    after_finish = api.post(
        logs_path,
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "8",
            "weight_kg": 10,
            "duration_seconds": 37,
            "session_id": started_session["id"],
        },
    )
    assert after_finish.status_code == 422
    assert api.delete(f"{logs_path}/{recorded.json()['id']}", headers=student).status_code == 422

    listed = api.get(sessions_path, headers=student)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    session = listed.json()[0]
    total_duration = parse_api_datetime(session["finished_at"]) - parse_api_datetime(session["started_at"])
    assert total_duration == timedelta(minutes=42, seconds=15)
    assert session["id"] == started_session["id"]
    assert session["day_name"] == "Día 1"

    logs = api.get(logs_path, headers=student)
    assert logs.status_code == 200
    assert len(logs.json()) == 1
    assert logs.json()[0]["duration_seconds"] == 37


def test_workout_sessions_are_independent_and_private_to_the_student(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    another_student = register_and_login(api, "another@example.com", "STUDENT")
    exercise_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")
    sessions_path = f"{ASSIGNED_PATH}/workout-sessions"
    logs_path = f"{ASSIGNED_PATH}/workout-logs"

    first = api.post(sessions_path, headers=student, json={"day_name": "Día 1"})
    assert first.status_code == 201
    first_id = first.json()["id"]
    first_log = api.post(
        logs_path,
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 10,
            "duration_seconds": 25,
            "session_id": first_id,
        },
    )
    assert first_log.status_code == 201
    removed = api.delete(f"{logs_path}/{first_log.json()['id']}", headers=student)
    assert removed.status_code == 204
    assert api.get(logs_path, headers=student).json() == []
    assert api.post(f"{sessions_path}/{first_id}/finish", headers=student).status_code == 200

    second = api.post(sessions_path, headers=student, json={"day_name": "Día 1"})
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert second_id != first_id
    second_log = api.post(
        logs_path,
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "9",
            "weight_kg": 12,
            "duration_seconds": 28,
            "session_id": second_id,
        },
    )
    assert second_log.status_code == 201
    assert api.post(f"{sessions_path}/{second_id}/finish", headers=student).status_code == 200

    listed = api.get(sessions_path, headers=student)
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {first_id, second_id}
    saved_logs = api.get(logs_path, headers=student).json()
    assert len(saved_logs) == 1
    assert saved_logs[0]["session_id"] == second_id
    assert saved_logs[0]["set_number"] == 1
    assert api.get(sessions_path, headers=another_student).json() == []
    assert api.post(f"{sessions_path}/{first_id}/finish", headers=another_student).status_code == 404
