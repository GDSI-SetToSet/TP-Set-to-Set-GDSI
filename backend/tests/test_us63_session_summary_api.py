"""US-63: resumen de la sesión finalizada."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.services.session_summary_service import parse_reps
from backend.tests.test_us60_rpe_api import (
    ASSIGNED_PATH,
    TEMPLATES_PATH,
    register_and_login,
    setup_routine_and_assignment,
)


def setup_student(api, sessions, suffix: str):
    trainer_email = f"trainer_us63_{suffix}@example.com"
    student_email = f"student_us63_{suffix}@example.com"
    trainer = register_and_login(api, trainer_email, "TRAINER")
    student = register_and_login(api, student_email, "STUDENT")
    exercise_id, rel_id, routine_id = setup_routine_and_assignment(
        api, sessions, trainer, student_email, trainer_email
    )
    return trainer, student, exercise_id, rel_id, routine_id


def start_session(api, student) -> str:
    response = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    assert response.status_code == 201
    return response.json()["id"]


def log_set(api, student, session_id: str, exercise_id: str, set_number: int, reps: str, weight: float):
    response = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": set_number,
            "reps_completed": reps,
            "weight_kg": weight,
            "session_id": session_id,
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def finish(api, student, session_id: str, rpe: int | None = None) -> None:
    payload = {"rpe": rpe} if rpe is not None else {}
    response = api.post(f"{ASSIGNED_PATH}/workout-sessions/{session_id}/finish", headers=student, json=payload)
    assert response.status_code == 200


def shift_session(sessions, session_id: str, days_ago: int, minutes: int = 45) -> None:
    """Mueve la sesión y sus series al pasado para controlar el orden histórico."""
    with sessions() as db:
        session = db.get(WorkoutSession, session_id)
        started = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
        session.started_at = started
        session.finished_at = started + timedelta(minutes=minutes)
        logs = db.scalars(select(WorkoutSetLog).where(WorkoutSetLog.session_id == session_id)).all()
        for index, log in enumerate(logs):
            log.recorded_at = started + timedelta(minutes=index + 1)
        db.commit()


def run_session(api, student, sessions, exercise_id: str, weights: list[float], days_ago: int, reps: str = "10"):
    session_id = start_session(api, student)
    for set_number, weight in enumerate(weights, start=1):
        log_set(api, student, session_id, exercise_id, set_number, reps, weight)
    finish(api, student, session_id)
    shift_session(sessions, session_id, days_ago)
    return session_id


def get_summary(api, student, session_id: str):
    return api.get(f"{ASSIGNED_PATH}/workout-sessions/{session_id}/summary", headers=student)


def test_parse_reps_variants():
    assert parse_reps("10") == 10
    assert parse_reps("8-10") == 8
    assert parse_reps("12,5") == 12.5
    assert parse_reps(" 6 reps") == 6
    assert parse_reps("al fallo") == 0
    assert parse_reps("") == 0
    assert parse_reps(None) == 0


def test_summary_shows_tonnage_duration_sets_and_rpe(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "basic")
    session_id = start_session(api, student)
    log_set(api, student, session_id, exercise_id, 1, "10", 20)
    log_set(api, student, session_id, exercise_id, 2, "8", 22.5)
    finish(api, student, session_id, rpe=7)
    shift_session(sessions, session_id, days_ago=0, minutes=30)

    response = get_summary(api, student, session_id)

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["day_name"] == "Día 1"
    assert data["total_tonnage_kg"] == 380.0
    assert data["duration_seconds"] == 30 * 60
    assert data["completed_sets"] == 2
    assert data["programmed_sets"] == 3
    assert data["rpe"] == 7
    assert data["history"] == {
        "previous_sessions_count": 0,
        "average_tonnage_kg": None,
        "tonnage_delta_percent": None,
    }


def test_summary_counts_bodyweight_and_non_numeric_reps_as_zero_tonnage(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "zero")
    session_id = start_session(api, student)
    log_set(api, student, session_id, exercise_id, 1, "12", 0)
    log_set(api, student, session_id, exercise_id, 2, "al fallo", 30)
    finish(api, student, session_id)

    data = get_summary(api, student, session_id).json()

    assert data["total_tonnage_kg"] == 0
    assert data["completed_sets"] == 2
    assert data["personal_records"][0]["weight_kg"] == 30


def test_summary_without_sets(client):
    api, sessions = client
    _, student, _, _, _ = setup_student(api, sessions, "empty")
    session_id = start_session(api, student)
    finish(api, student, session_id)

    data = get_summary(api, student, session_id).json()

    assert data["total_tonnage_kg"] == 0
    assert data["completed_sets"] == 0
    assert data["personal_records"] == []
    assert data["rpe"] is None


def test_summary_highlights_initial_and_improved_personal_records(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "prs")
    first = run_session(api, student, sessions, exercise_id, [20, 25], days_ago=3)
    second = run_session(api, student, sessions, exercise_id, [27.5, 26], days_ago=1)

    first_records = get_summary(api, student, first).json()["personal_records"]
    second_records = get_summary(api, student, second).json()["personal_records"]

    assert first_records == [
        {
            "exercise_id": exercise_id,
            "exercise_name": "Press militar",
            "weight_kg": 25.0,
            "reps_completed": "10",
            "previous_weight_kg": None,
        }
    ]
    assert second_records[0]["weight_kg"] == 27.5
    assert second_records[0]["previous_weight_kg"] == 25.0


def test_summary_keeps_pr_even_if_beaten_in_a_later_session(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "beaten")
    first = run_session(api, student, sessions, exercise_id, [30], days_ago=5)
    run_session(api, student, sessions, exercise_id, [40], days_ago=2)

    records = get_summary(api, student, first).json()["personal_records"]

    assert len(records) == 1
    assert records[0]["weight_kg"] == 30


def test_summary_without_new_personal_record(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "nopr")
    run_session(api, student, sessions, exercise_id, [40], days_ago=4)
    second = run_session(api, student, sessions, exercise_id, [40, 35], days_ago=1)

    assert get_summary(api, student, second).json()["personal_records"] == []


def test_summary_compares_against_previous_sessions_of_same_day(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "history")
    run_session(api, student, sessions, exercise_id, [20], days_ago=6)  # 200 kg
    run_session(api, student, sessions, exercise_id, [30], days_ago=4)  # 300 kg
    empty = start_session(api, student)  # sin series: no entra en el promedio
    finish(api, student, empty)
    shift_session(sessions, empty, days_ago=3)
    current = run_session(api, student, sessions, exercise_id, [25, 25], days_ago=1)  # 500 kg

    history = get_summary(api, student, current).json()["history"]

    assert history == {
        "previous_sessions_count": 2,
        "average_tonnage_kg": 250.0,
        "tonnage_delta_percent": 100.0,
    }


def test_summary_ignores_later_sessions_in_history(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "later")
    first = run_session(api, student, sessions, exercise_id, [20], days_ago=5)
    run_session(api, student, sessions, exercise_id, [30], days_ago=2)

    assert get_summary(api, student, first).json()["history"]["previous_sessions_count"] == 0


def test_summary_delta_is_null_when_previous_average_is_zero(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "zeroavg")
    run_session(api, student, sessions, exercise_id, [0], days_ago=3)
    current = run_session(api, student, sessions, exercise_id, [20], days_ago=1)

    history = get_summary(api, student, current).json()["history"]

    assert history["previous_sessions_count"] == 1
    assert history["average_tonnage_kg"] == 0
    assert history["tonnage_delta_percent"] is None


def test_programmed_sets_is_null_when_routine_changed(client):
    api, sessions = client
    trainer, student, exercise_id, rel_id, _ = setup_student(api, sessions, "changed")
    session_id = run_session(api, student, sessions, exercise_id, [20], days_ago=1)
    other = api.post(
        TEMPLATES_PATH,
        headers=trainer,
        json={
            "name": "Otra rutina",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": "Día A",
                    "blocks": [
                        {
                            "name": "Bloque",
                            "exercises": [{"exercise_id": exercise_id, "sets": 4, "reps": "8", "rest_seconds": 60}],
                        }
                    ],
                }
            ],
        },
    )
    assert other.status_code == 201
    reassigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": other.json()["id"]},
    )
    assert reassigned.status_code == 200

    data = get_summary(api, student, session_id).json()

    assert data["programmed_sets"] is None
    assert data["completed_sets"] == 1


def test_programmed_sets_is_null_without_active_routine(client):
    api, sessions = client
    trainer, student, exercise_id, rel_id, _ = setup_student(api, sessions, "unassigned")
    session_id = run_session(api, student, sessions, exercise_id, [20], days_ago=1)
    unassigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": None},
    )
    assert unassigned.status_code == 200

    assert get_summary(api, student, session_id).json()["programmed_sets"] is None


def test_programmed_sets_is_null_when_day_no_longer_exists(client):
    api, sessions = client
    _, student, exercise_id, _, _ = setup_student(api, sessions, "renamed")
    session_id = run_session(api, student, sessions, exercise_id, [20], days_ago=1)
    with sessions() as db:
        db.get(WorkoutSession, session_id).day_name = "Día eliminado"
        db.commit()

    assert get_summary(api, student, session_id).json()["programmed_sets"] is None


def test_summary_rejects_unfinished_session(client):
    api, sessions = client
    _, student, _, _, _ = setup_student(api, sessions, "active")
    session_id = start_session(api, student)

    response = get_summary(api, student, session_id)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "finalizás" in response.json()["detail"]


def test_summary_of_another_student_is_not_found(client):
    api, sessions = client
    _, owner, exercise_id, _, _ = setup_student(api, sessions, "owner")
    session_id = run_session(api, owner, sessions, exercise_id, [20], days_ago=1)
    _, intruder, _, _, _ = setup_student(api, sessions, "intruder")

    assert get_summary(api, intruder, session_id).status_code == 404
    assert get_summary(api, owner, "no-existe").status_code == 404


def test_summary_requires_student_role(client):
    api, sessions = client
    trainer, student, exercise_id, _, _ = setup_student(api, sessions, "role")
    session_id = run_session(api, student, sessions, exercise_id, [20], days_ago=1)

    assert get_summary(api, trainer, session_id).status_code == 403
    assert api.get(f"{ASSIGNED_PATH}/workout-sessions/{session_id}/summary").status_code == 401
