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


def test_previous_session_continuity_across_template_to_student_routine_conversion(client, monkeypatch):
    """DEF-01: convertir RoutineTemplate a StudentRoutine (vía US-26/US-14) no rompe previous_session en US-24."""
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 10, 13, 0, tzinfo=UTC))
    s1_id = run_session(api, student, clock, exercise_id, [(10, 30), (10, 30)])

    # Primer ajuste US-26: crea StudentRoutine con un nuevo id
    adj_resp = api.put(
        f"/api/v1/trainers/me/sessions/{s1_id}/adjustment",
        headers=trainer,
        json={
            "blocks": [
                {
                    "name": "Principal",
                    "exercises": [
                        {"exercise_id": exercise_id, "sets": 4, "reps": "8", "rest_seconds": 60, "target_weight_kg": 12.5}
                    ],
                }
            ],
            "note": "Subimos una serie",
        },
    )
    assert adj_resp.status_code == 200

    clock["now"] = datetime(2026, 11, 12, 13, 0, tzinfo=UTC)
    s2_id = run_session(api, student, clock, exercise_id, [(12.5, 35), (12.5, 40)])

    body = api.get(comparison_path(s2_id), headers=trainer).json()
    assert body["previous_session"] is not None
    assert body["previous_session"]["id"] == s1_id
    assert body["previous_volume_kg"] == 8 * 20
    assert body["exercises"][0]["planned"] == {"sets": 4, "reps": "8", "target_weight_kg": 12.5}
    assert body["exercises"][0]["previous"]["sets_completed"] == 2


def test_reassignment_isolates_history_from_previous_routine_assignment(client, monkeypatch):
    """DEF-11: reasignar una nueva rutina con igual nombre de día no mezcla previous_session en US-24."""
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, relationship_id = create_assigned_routine(api, sessions, trainer, "student@example.com")
    student_id = api.get("/api/v1/routine-templates/assignments", headers=trainer).json()[0]["student_id"]

    # Forzar creación previa de StudentRoutine (US-14)
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/routine", headers=trainer).status_code == 200

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 10, 13, 0, tzinfo=UTC))
    s1_id = run_session(api, student, clock, exercise_id, [(10, 30)])

    # Crear y reasignar una rutina completamente nueva que también tiene "Día 1"
    other_tpl = api.post(
        "/api/v1/routine-templates",
        headers=trainer,
        json={
            "name": "Rutina Nueva",
            "duration_weeks": 6,
            "intensity": "ALTA",
            "days": [
                {
                    "name": "Día 1",
                    "blocks": [
                        {
                            "name": "Principal",
                            "exercises": [
                                {"exercise_id": exercise_id, "sets": 5, "reps": "5", "rest_seconds": 90, "target_weight_kg": 20}
                            ],
                        }
                    ],
                }
            ],
        },
    ).json()
    assert api.put(
        f"/api/v1/routine-templates/assignments/{relationship_id}",
        headers=trainer,
        json={"routine_template_id": other_tpl["id"]},
    ).status_code == 200

    clock["now"] = datetime(2026, 11, 12, 13, 0, tzinfo=UTC)
    s2_id = run_session(api, student, clock, exercise_id, [(20, 40)])

    body = api.get(comparison_path(s2_id), headers=trainer).json()
    assert body["previous_session"] is None
    assert body["previous_volume_kg"] is None
    assert body["exercises"][0]["previous"] is None
    # S1 pertenece a la asignación anterior, así que US-26 tampoco debe permitir ajustar la rutina nueva desde S1
    blocked = api.get(f"/api/v1/trainers/me/sessions/{s1_id}/adjustment", headers=trainer)
    assert blocked.status_code == 200
    assert blocked.json()["can_adjust"] is False


def test_historical_planned_metrics_are_preserved_after_subsequent_adjustment(client, monkeypatch):
    """DEF-02: ajustar la próxima sesión en US-26 no altera los valores planificados de sesiones históricas."""
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")
    student_id = api.get("/api/v1/routine-templates/assignments", headers=trainer).json()[0]["student_id"]

    # Materializar StudentRoutine (US-14) antes de S1, así S1 apunta al StudentRoutine mutable
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/routine", headers=trainer).status_code == 200

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 10, 13, 0, tzinfo=UTC))
    s1_id = run_session(api, student, clock, exercise_id, [(10, 30), (10, 30), (10, 30)])

    # Ajustar la próxima sesión a 5 series x 10 reps x 25 kg
    adj = api.put(
        f"/api/v1/trainers/me/sessions/{s1_id}/adjustment",
        headers=trainer,
        json={
            "blocks": [
                {
                    "name": "Principal",
                    "exercises": [
                        {"exercise_id": exercise_id, "sets": 5, "reps": "10", "rest_seconds": 60, "target_weight_kg": 25}
                    ],
                }
            ]
        },
    )
    assert adj.status_code == 200

    body = api.get(comparison_path(s1_id), headers=trainer).json()
    assert body["exercises"][0]["planned"] == {"sets": 3, "reps": "8", "target_weight_kg": 10.0}


def test_duration_comparison_and_missing_duration_distinction(client, monkeypatch):
    """DEF-07: expone planned_duration_seconds de los bloques y distingue duration_seconds=None de 0."""
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    ex_no_dur = api.post(
        "/api/v1/exercises",
        headers=trainer,
        json={
            "name": "Sentadilla",
            "description": "Piernas",
            "category": "FUERZA",
            "target_muscle_group": "Piernas",
            "equipment_needed": "Barra",
        },
    ).json()["id"]
    ex_zero_dur = api.post(
        "/api/v1/exercises",
        headers=trainer,
        json={
            "name": "Plancha",
            "description": "Core",
            "category": "FUERZA",
            "target_muscle_group": "Core",
            "equipment_needed": "Ninguno",
        },
    ).json()["id"]
    tpl = api.post(
        "/api/v1/routine-templates",
        headers=trainer,
        json={
            "name": "Rutina con duración",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": "Día 1",
                    "blocks": [
                        {
                            "name": "Principal",
                            "estimated_duration_minutes": 30,
                            "exercises": [
                                {"exercise_id": ex_no_dur, "sets": 1, "reps": "8", "rest_seconds": 60, "target_weight_kg": 20},
                                {"exercise_id": ex_zero_dur, "sets": 1, "reps": "30", "rest_seconds": 45, "target_weight_kg": 0},
                            ],
                        }
                    ],
                }
            ],
        },
    ).json()["id"]
    from backend.tests.test_workout_session_api import link_student

    rel_id = link_student(sessions, "trainer@example.com", "student@example.com")
    assert api.put(
        f"/api/v1/routine-templates/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": tpl},
    ).status_code == 200

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 13, 0, tzinfo=UTC))
    sess = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    # Serie 1 sin duration_seconds (None)
    assert api.post(
        "/api/v1/students/me/routine-templates/assigned/workout-logs",
        headers=student,
        json={
            "exercise_id": ex_no_dur,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 20,
            "session_id": sess["id"],
        },
    ).status_code == 201
    # Serie 2 con duration_seconds explícito = 0
    assert api.post(
        "/api/v1/students/me/routine-templates/assigned/workout-logs",
        headers=student,
        json={
            "exercise_id": ex_zero_dur,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "30",
            "weight_kg": 0,
            "duration_seconds": 0,
            "session_id": sess["id"],
        },
    ).status_code == 201
    clock["now"] += timedelta(minutes=25)
    assert api.post(f"{SESSIONS_PATH}/{sess['id']}/finish", headers=student).status_code == 200

    body = api.get(comparison_path(sess["id"]), headers=trainer).json()
    assert body["planned_duration_seconds"] == 30 * 60
    by_id = {ex["exercise_id"]: ex for ex in body["exercises"]}
    assert by_id[ex_no_dur]["performed"]["total_duration_seconds"] is None
    assert by_id[ex_zero_dur]["performed"]["total_duration_seconds"] == 0


def test_two_sessions_same_utc_day_keep_independent_replacements(client, monkeypatch):
    """DEF-08: dos sesiones del mismo día UTC conservan sus reemplazos separados por session_id."""
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    squat_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")
    alt1 = api.post(
        "/api/v1/exercises",
        headers=trainer,
        json={"name": "Estocada", "description": "Piernas", "category": "FUERZA", "target_muscle_group": "Piernas", "equipment_needed": "Mancuerna"},
    ).json()["id"]
    alt2 = api.post(
        "/api/v1/exercises",
        headers=trainer,
        json={"name": "Prensa", "description": "Piernas", "category": "FUERZA", "target_muscle_group": "Piernas", "equipment_needed": "Máquina"},
    ).json()["id"]

    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 8, 0, tzinfo=UTC))
    from backend.src.services import exercise_alternative_service

    monkeypatch.setattr(exercise_alternative_service, "utc_now", lambda: clock["now"])

    # Sesión 1 reemplaza Sentadilla por Estocada
    s1 = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    assert api.put(
        "/api/v1/students/me/exercise-replacements",
        headers=student,
        json={"day_name": "Día 1", "original_exercise_id": squat_id, "replacement_exercise_id": alt1, "session_id": s1["id"]},
    ).status_code == 200
    log_set(api, student, alt1, s1["id"], 1, 10, 30)
    clock["now"] += timedelta(minutes=20)
    assert api.post(f"{SESSIONS_PATH}/{s1['id']}/finish", headers=student).status_code == 200

    # Sesión 2 el mismo día UTC reemplaza Sentadilla por Prensa
    clock["now"] += timedelta(hours=4)
    s2 = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    assert api.put(
        "/api/v1/students/me/exercise-replacements",
        headers=student,
        json={"day_name": "Día 1", "original_exercise_id": squat_id, "replacement_exercise_id": alt2, "session_id": s2["id"]},
    ).status_code == 200
    log_set(api, student, alt2, s2["id"], 1, 50, 30)
    clock["now"] += timedelta(minutes=20)
    assert api.post(f"{SESSIONS_PATH}/{s2['id']}/finish", headers=student).status_code == 200

    comp1 = api.get(comparison_path(s1["id"]), headers=trainer).json()
    comp2 = api.get(comparison_path(s2["id"]), headers=trainer).json()
    assert comp1["exercises"][0]["exercise_id"] == alt1
    assert comp1["exercises"][0]["replaced_exercise_name"] == "Sentadilla"
    assert comp2["exercises"][0]["exercise_id"] == alt2
    assert comp2["exercises"][0]["replaced_exercise_name"] == "Sentadilla"

    adj1 = api.get(f"/api/v1/trainers/me/sessions/{s1['id']}/adjustment", headers=trainer).json()
    adj2 = api.get(f"/api/v1/trainers/me/sessions/{s2['id']}/adjustment", headers=trainer).json()
    assert adj1["replacement_requests"][0]["replacement_exercise_name"] == "Estocada"
    assert adj2["replacement_requests"][0]["replacement_exercise_name"] == "Prensa"
