from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from backend.src.models.exercise import Exercise
from backend.src.models.exercise_replacement_log import ExerciseReplacementLog
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.tests.test_us22_daily_routines_api import (
    SESSIONS_PATH,
    fixed_clock,
    log_set,
)
from backend.tests.test_workout_session_api import (
    create_assigned_routine,
    register_and_login,
)


def comparison_path(session_id: str) -> str:
    return f"/api/v1/trainers/me/sessions/{session_id}/comparison"


def run_session(api, student, clock, exercise_id: str, sets: list[tuple[float, int]]) -> str:
    session = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    for number, (weight, seconds) in enumerate(sets, start=1):
        clock["now"] += timedelta(minutes=2)
        log_set(api, student, exercise_id, session["id"], number, weight, seconds)
    clock["now"] += timedelta(minutes=30)
    assert api.post(f"{SESSIONS_PATH}/{session['id']}/finish", headers=student, json={"rpe": 7}).status_code == 200
    return session["id"]


def test_finished_session_is_compared_with_plan_and_previous_session_of_the_same_day(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 10, 13, 0, tzinfo=UTC))
    previous_id = run_session(api, student, clock, exercise_id, [(10, 30), (10, 30)])
    clock["now"] = datetime(2026, 11, 11, 13, 0, tzinfo=UTC)
    api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"})  # sesión abandonada: no cuenta como previa
    clock["now"] = datetime(2026, 11, 12, 13, 0, tzinfo=UTC)
    current_id = run_session(api, student, clock, exercise_id, [(12.5, 35), (12.5, 40), (15, 45)])

    response = api.get(comparison_path(current_id), headers=trainer)

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["id"] == current_id
    assert body["session"]["rpe"] == 7
    assert body["previous_session"]["id"] == previous_id
    assert body["volume_kg"] == 8 * (12.5 + 12.5 + 15)
    assert body["previous_volume_kg"] == 8 * 20
    [exercise] = body["exercises"]
    assert exercise["exercise_name"] == "Sentadilla"
    assert exercise["replaced_exercise_name"] is None
    assert exercise["planned"] == {"sets": 3, "reps": "8", "target_weight_kg": 10.0}
    assert exercise["performed"] == {
        "sets_completed": 3,
        "reps": ["8", "8", "8"],
        "max_weight_kg": 15.0,
        "volume_kg": 320.0,
        "total_duration_seconds": 120,
    }
    assert exercise["previous"]["sets_completed"] == 2
    assert exercise["previous"]["max_weight_kg"] == 10.0


def test_first_session_has_no_previous_and_unlogged_planned_exercises_show_no_performance(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    create_assigned_routine(api, sessions, trainer, "student@example.com")

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 13, 0, tzinfo=UTC))
    session = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    clock["now"] += timedelta(minutes=20)
    api.post(f"{SESSIONS_PATH}/{session['id']}/finish", headers=student)

    body = api.get(comparison_path(session["id"]), headers=trainer).json()

    assert body["previous_session"] is None
    assert body["previous_volume_kg"] is None
    assert body["volume_kg"] == 0
    [exercise] = body["exercises"]
    assert exercise["exercise_name"] == "Sentadilla"
    assert exercise["planned"]["sets"] == 3
    assert exercise["performed"] is None
    assert exercise["previous"] is None


def test_replacement_is_compared_against_the_original_plan_and_extra_exercises_are_listed(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    squat_id, relationship_id = create_assigned_routine(api, sessions, trainer, "student@example.com")

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 13, 0, tzinfo=UTC))
    session = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    clock["now"] += timedelta(minutes=30)
    api.post(f"{SESSIONS_PATH}/{session['id']}/finish", headers=student)

    with sessions() as db:
        squat = db.get(Exercise, squat_id)
        stored = db.get(WorkoutSession, session["id"])
        lunge = Exercise(
            trainer_id=squat.trainer_id,
            name="Estocada",
            description="Zancada",
            category="FUERZA",
            target_muscle_group="Piernas",
            equipment_needed="Mancuerna",
            created_at=datetime(2026, 11, 12),
            updated_at=datetime(2026, 11, 12),
        )
        plank = Exercise(
            trainer_id=squat.trainer_id,
            name="Plancha",
            description="Core",
            category="FUERZA",
            target_muscle_group="Core",
            equipment_needed="Ninguno",
            created_at=datetime(2026, 11, 12),
            updated_at=datetime(2026, 11, 12),
        )
        db.add_all([lunge, plank])
        db.flush()
        db.add(
            ExerciseReplacementLog(
                student_id=stored.student_id,
                routine_id=stored.routine_id,
                day_name="Día 1",
                session_date=date(2026, 11, 12),
                original_exercise_id=squat_id,
                replacement_exercise_id=lunge.id,
                updated_at=datetime(2026, 11, 12, 13, 5),
            )
        )
        for exercise, reps, weight in ((lunge, "10", Decimal(8)), (plank, "al fallo", None)):
            db.add(
                WorkoutSetLog(
                    student_id=stored.student_id,
                    relationship_id=relationship_id,
                    routine_id=stored.routine_id,
                    day_name="Día 1",
                    exercise_id=exercise.id,
                    exercise_name=exercise.name,
                    set_number=1,
                    reps_completed=reps,
                    weight_kg=weight,
                    duration_seconds=30,
                    session_id=stored.id,
                    recorded_at=datetime(2026, 11, 12, 13, 10),
                )
            )
        db.commit()

    body = api.get(comparison_path(session["id"]), headers=trainer).json()

    replaced, extra = body["exercises"]
    assert replaced["exercise_name"] == "Estocada"
    assert replaced["replaced_exercise_name"] == "Sentadilla"
    assert replaced["planned"]["sets"] == 3
    assert replaced["performed"]["volume_kg"] == 80.0
    assert extra["exercise_name"] == "Plancha"
    assert extra["planned"] is None
    assert extra["performed"]["reps"] == ["al fallo"]
    assert extra["performed"]["max_weight_kg"] is None
    assert extra["performed"]["volume_kg"] == 0
    assert body["volume_kg"] == 80.0


def test_planned_values_follow_the_student_routine_copy(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")
    student_id = api.get("/api/v1/routine-templates/assignments", headers=trainer).json()[0]["student_id"]
    base = f"/api/v1/trainers/me/students/{student_id}/routine"
    routine = api.get(base, headers=trainer)
    assert routine.status_code == 200
    days = [
        {
            "name": "Día 1",
            "blocks": [
                {
                    "name": "Principal",
                    "exercises": [
                        {"exercise_id": exercise_id, "sets": 4, "reps": "6", "rest_seconds": 90, "target_weight_kg": 20}
                    ],
                }
            ],
        }
    ]
    draft = {
        "name": "Rutina de prueba",
        "duration_weeks": 4,
        "intensity": "MEDIA",
        "has_no_materials_alternative": False,
        "days": days,
        "draft_version": routine.json().get("draft_version", 0),
    }
    assert api.put(f"{base}/draft", headers=trainer, json=draft).status_code == 200
    assert api.post(f"{base}/draft/confirm", headers=trainer).status_code == 200

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 13, 0, tzinfo=UTC))
    session_id = run_session(api, student, clock, exercise_id, [(20, 30)])

    [exercise] = api.get(comparison_path(session_id), headers=trainer).json()["exercises"]
    assert exercise["planned"] == {"sets": 4, "reps": "6", "target_weight_kg": 20.0}


def test_comparison_requires_a_finished_session_of_an_own_active_student(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    other_trainer = register_and_login(api, "other-trainer@example.com", "TRAINER")
    create_assigned_routine(api, sessions, trainer, "student@example.com")
    fixed_clock(monkeypatch, datetime(2026, 11, 12, 13, 0, tzinfo=UTC))
    session = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()

    in_progress = api.get(comparison_path(session["id"]), headers=trainer)
    assert in_progress.status_code == 409
    assert "en curso" in in_progress.json()["detail"]
    assert api.get(comparison_path(session["id"]), headers=other_trainer).status_code == 404
    assert api.get(comparison_path("no-existe"), headers=trainer).status_code == 404
    assert api.get(comparison_path(session["id"]), headers=student).status_code in (403, 404)
    assert api.get(comparison_path(session["id"])).status_code == 401

    with sessions() as db:
        assert db.scalar(select(WorkoutSession.id).where(WorkoutSession.id == session["id"])) is not None
