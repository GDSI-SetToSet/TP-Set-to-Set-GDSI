from datetime import UTC, datetime, timedelta

from backend.src.services import routine_template_service
from backend.tests.test_workout_session_api import (
    ASSIGNED_PATH,
    create_assigned_routine,
    register_and_login,
)

DAILY_PATH = "/api/v1/trainers/me/daily-routines"
SESSIONS_PATH = f"{ASSIGNED_PATH}/workout-sessions"
LOGS_PATH = f"{ASSIGNED_PATH}/workout-logs"


def fixed_clock(monkeypatch, start: datetime) -> dict[str, datetime]:
    clock = {"now": start}
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: clock["now"])
    return clock


def log_set(api, headers, exercise_id: str, session_id: str, set_number: int, weight: float, seconds: int):
    response = api.post(
        LOGS_PATH,
        headers=headers,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": set_number,
            "reps_completed": "8",
            "weight_kg": weight,
            "duration_seconds": seconds,
            "session_id": session_id,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_daily_routines_show_status_and_set_details_per_student(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    finished_student = register_and_login(api, "finished@example.com", "STUDENT")
    training_student = register_and_login(api, "training@example.com", "STUDENT")
    register_and_login(api, "idle@example.com", "STUDENT")
    exercise_id, finished_rel = create_assigned_routine(api, sessions, trainer, "finished@example.com")
    training_exercise_id, training_rel = create_assigned_routine(api, sessions, trainer, "training@example.com")
    _, idle_rel = create_assigned_routine(api, sessions, trainer, "idle@example.com")

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 13, 0, tzinfo=UTC))
    finished_session = api.post(SESSIONS_PATH, headers=finished_student, json={"day_name": "Día 1"}).json()
    clock["now"] += timedelta(minutes=5)
    log_set(api, finished_student, exercise_id, finished_session["id"], 2, 22.5, 40)
    log_set(api, finished_student, exercise_id, finished_session["id"], 1, 20, 35)
    clock["now"] += timedelta(minutes=40)
    finish = api.post(f"{SESSIONS_PATH}/{finished_session['id']}/finish", headers=finished_student)
    assert finish.status_code == 200

    training_session = api.post(SESSIONS_PATH, headers=training_student, json={"day_name": "Día 1"}).json()
    log_set(api, training_student, training_exercise_id, training_session["id"], 1, 15, 30)

    response = api.get(DAILY_PATH, headers=trainer, params={"date": "2026-11-12", "utc_offset_minutes": -180})

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 3
    statuses = {item["relationship_id"]: item["status"] for item in items}
    assert statuses == {finished_rel: "FINISHED", training_rel: "TRAINING", idle_rel: "NOT_STARTED"}

    finished = next(item for item in items if item["relationship_id"] == finished_rel)
    assert finished["routine_name"] == "Rutina de prueba"
    assert finished["session"]["day_name"] == "Día 1"
    assert finished["session"]["duration_seconds"] == 45 * 60
    assert [ex["exercise_name"] for ex in finished["exercises"]] == ["Sentadilla"]
    sets = finished["exercises"][0]["sets"]
    assert [(s["set_number"], s["weight_kg"], s["duration_seconds"]) for s in sets] == [(1, 20.0, 35), (2, 22.5, 40)]
    assert all(s["recorded_at"].endswith(("+00:00", "Z")) for s in sets)

    training = next(item for item in items if item["relationship_id"] == training_rel)
    assert training["session"]["finished_at"] is None
    assert training["session"]["duration_seconds"] is None
    assert training["exercises"][0]["sets"][0]["weight_kg"] == 15.0

    idle = next(item for item in items if item["relationship_id"] == idle_rel)
    assert idle["session"] is None
    assert idle["exercises"] == []


def test_daily_routines_only_consider_the_requested_local_day(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    _, relationship_id = create_assigned_routine(api, sessions, trainer, "student@example.com")

    # 01:30 UTC del 13/11 equivale a las 22:30 del 12/11 en UTC-3.
    fixed_clock(monkeypatch, datetime(2026, 11, 13, 1, 30, tzinfo=UTC))
    api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"})

    local_day = api.get(DAILY_PATH, headers=trainer, params={"date": "2026-11-12", "utc_offset_minutes": -180})
    next_day = api.get(DAILY_PATH, headers=trainer, params={"date": "2026-11-13", "utc_offset_minutes": -180})

    assert local_day.json()[0]["relationship_id"] == relationship_id
    assert local_day.json()[0]["status"] == "TRAINING"
    assert next_day.json()[0]["status"] == "NOT_STARTED"


def test_in_progress_session_takes_priority_over_an_earlier_finished_one(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    create_assigned_routine(api, sessions, trainer, "student@example.com")

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 12, 0, tzinfo=UTC))
    first = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    clock["now"] += timedelta(minutes=30)
    api.post(f"{SESSIONS_PATH}/{first['id']}/finish", headers=student)
    clock["now"] += timedelta(hours=2)
    second = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()

    items = api.get(DAILY_PATH, headers=trainer, params={"date": "2026-11-12"}).json()

    assert items[0]["status"] == "TRAINING"
    assert items[0]["session"]["id"] == second["id"]


def test_daily_routines_are_private_and_validate_parameters(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    register_and_login(api, "student@example.com", "STUDENT")
    create_assigned_routine(api, sessions, trainer, "student@example.com")
    other_trainer = register_and_login(api, "other-trainer@example.com", "TRAINER")
    student = register_and_login(api, "student-only@example.com", "STUDENT")

    assert api.get(DAILY_PATH, headers=other_trainer).json() == []
    assert len(api.get(DAILY_PATH, headers=trainer).json()) == 1
    assert api.get(DAILY_PATH, headers=student).status_code in (403, 404)
    assert api.get(DAILY_PATH, headers=trainer, params={"utc_offset_minutes": 2000}).status_code == 422
    assert api.get(DAILY_PATH, headers=trainer, params={"date": "no-es-fecha"}).status_code == 422
    assert api.get(DAILY_PATH).status_code == 401
