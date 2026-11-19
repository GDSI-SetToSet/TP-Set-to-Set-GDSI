from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.src.models.exercise import Exercise
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.tests.test_us22_daily_routines_api import fixed_clock
from backend.tests.test_workout_session_api import (
    create_assigned_routine,
    register_and_login,
)

PATH = "/api/v1/students/me/progress"
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)  # sábado; la semana en curso empieza el lunes 9/11
WEEK = timedelta(weeks=1)


def setup(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    squat, relationship_id = create_assigned_routine(api, sessions, trainer, "student@example.com")
    fixed_clock(monkeypatch, NOW)
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        relationship.routine_assigned_at = (NOW - 20 * WEEK).replace(tzinfo=None)
        student_id = relationship.student_id
        trainer_id = db.get(Exercise, squat).trainer_id
        ids = {}
        for name, group in [("Press banca", "Pecho"), ("Curl femoral", "Piernas"), ("Dominadas", "Espalda")]:
            ex = Exercise(
                name=name, description="x", category="FUERZA", target_muscle_group=group, equipment_needed="Barra",
                trainer_id=trainer_id, created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
            )
            db.add(ex)
            db.flush()
            ids[name] = ex.id
        db.commit()

    def add(exercise_id, weeks_ago, weight, reps="8", set_number=1, day_offset=0):
        moment = (NOW - weeks_ago * WEEK + timedelta(days=day_offset)).replace(tzinfo=None)
        with sessions() as db:
            db.add(WorkoutSetLog(
                student_id=student_id, relationship_id=relationship_id, routine_id="r", day_name="Día 1",
                exercise_id=exercise_id, exercise_name="x", set_number=set_number, reps_completed=reps,
                weight_kg=Decimal(str(weight)) if weight is not None else None, recorded_at=moment,
            ))
            db.commit()

    def finish(weeks_ago, day_offset=0):
        moment = (NOW - weeks_ago * WEEK + timedelta(days=day_offset)).replace(tzinfo=None)
        with sessions() as db:
            db.add(WorkoutSession(
                student_id=student_id, relationship_id=relationship_id, routine_id="r", day_name="Día 1",
                modality="GYM", started_at=moment, finished_at=moment,
            ))
            db.commit()

    return api, trainer, student, squat, ids, add, finish


def get(api, student, **params):
    return api.get(PATH, headers=student, params=params)


def by_name(body):
    return {e["name"]: e for e in body["exercises"]}


def test_message_key_for_each_case_and_order(client, monkeypatch):
    api, _, student, squat, ids, add, _ = setup(client, monkeypatch)
    add(squat, 4, 22.5)
    add(squat, 1, 40)  # subió el peso
    add(ids["Press banca"], 3, 30, reps="8")
    add(ids["Press banca"], 1, 30, reps="10")  # mismo peso, más repeticiones
    for weeks_ago in (3, 2, 1):
        add(ids["Curl femoral"], weeks_ago, 40)  # sin cambios
    add(ids["Dominadas"], 3, None, reps="6")
    add(ids["Dominadas"], 1, None, reps="9")  # sin carga
    body = get(api, student).json()
    found = by_name(body)

    assert found["Sentadilla"]["message_key"] == "weight_increased"
    assert (found["Sentadilla"]["start"]["weight"], found["Sentadilla"]["current"]["weight"]) == (22.5, 40.0)
    assert found["Sentadilla"]["last_improvement_is_pr"] is True
    assert found["Press banca"]["message_key"] == "reps_increased"
    assert found["Curl femoral"]["message_key"] == "no_change" and found["Curl femoral"]["weeks_without_change"] >= 1
    assert found["Dominadas"]["message_key"] == "bodyweight_reps_increased" and found["Dominadas"]["metric"] == "max_reps"
    # primero las mejoras, después el resto por orden alfabético
    assert [e["name"] for e in body["exercises"]] == ["Dominadas", "Press banca", "Sentadilla", "Curl femoral"]
    assert body["summary"]["improving_exercises_last_4w"] == 3


def test_below_best_few_data_and_current_week_excluded(client, monkeypatch):
    api, _, student, squat, ids, add, _ = setup(client, monkeypatch)
    add(squat, 3, 50)
    add(squat, 2, 50)
    add(squat, 1, 45)  # <= 90 % de la mejor
    add(ids["Press banca"], 0, 60, day_offset=-3)  # un solo día, semana en curso
    add(ids["Curl femoral"], 3, 30)
    add(ids["Curl femoral"], 0, 80, day_offset=-3)  # la semana en curso no cuenta como mejora
    found = by_name(get(api, student).json())
    assert found["Sentadilla"]["message_key"] == "below_best" and found["Sentadilla"]["best"]["weight"] == 50.0
    assert found["Press banca"]["message_key"] == "few_data"
    assert found["Curl femoral"]["message_key"] == "few_data"  # 1 sola semana completa


def test_records_exclude_first_load_and_use_previous_mark(client, monkeypatch):
    api, _, student, squat, ids, add, _ = setup(client, monkeypatch)
    add(squat, 9, 35)  # primera carga: no es récord
    add(squat, 6, 35, reps="10")  # mismo peso, más repeticiones
    add(squat, 2, 35, reps="9")  # no supera
    add(squat, 1, 40, reps="8")
    add(ids["Press banca"], 1, 40)  # primera carga
    body = get(api, student).json()

    assert [(r["name"], r["weight"], r["reps"], r["previous"]) for r in body["records"]] == [
        ("Sentadilla", 40.0, 8, {"weight": 35.0, "reps": 10}),
        ("Sentadilla", 35.0, 10, {"weight": 35.0, "reps": 8}),
    ]
    assert [r["date"] for r in body["records"]] == sorted((r["date"] for r in body["records"]), reverse=True)
    assert body["summary"]["records_in_period"] == 2
    assert [p["is_pr"] for p in by_name(body)["Sentadilla"]["points"]] == [False, True, False, True]
    assert {n["name"] for n in body["new_exercises"]} == {"Sentadilla", "Press banca"}

    short = get(api, student, period="4w").json()  # la marca previa sale del historial completo
    assert [(r["weight"], r["previous"]["weight"]) for r in short["records"]] == [(40.0, 35.0)]


def test_muscle_group_filter_keeps_chips_and_summary(client, monkeypatch):
    api, _, student, squat, ids, add, _ = setup(client, monkeypatch)
    add(squat, 3, 50)
    add(squat, 1, 60)
    add(ids["Press banca"], 3, 40)
    add(ids["Press banca"], 1, 45)
    body = get(api, student, muscle_group="Pecho").json()
    assert [e["name"] for e in body["exercises"]] == ["Press banca"]
    assert [r["name"] for r in body["records"]] == ["Press banca"]
    assert body["muscle_groups"] == ["Pecho", "Piernas"]
    assert body["summary"]["records_in_period"] == 2 and body["summary"]["improving_exercises_last_4w"] == 2
    assert get(api, student, muscle_group="Espalda").json()["exercises"] == []


def test_consistency_excludes_current_week_and_computes_streak(client, monkeypatch):
    api, _, student, squat, _, add, finish = setup(client, monkeypatch)
    add(squat, 1, 50)
    for weeks_ago in (5, 4, 3, 1):  # la semana de hace 2 queda sin sesiones
        finish(weeks_ago)
    finish(0, day_offset=-3)  # semana en curso
    body = get(api, student, period="4w").json()

    weeks = body["consistency"]
    assert len(weeks) == 4 and weeks[-1]["is_partial"] is True and weeks[-1]["completed"] == 1
    assert [w["completed"] for w in weeks[:-1]] == [1, 0, 1]
    assert body["summary"]["streak"] == {"current_weeks": 1, "best_weeks": 3}  # el historial completo, sin la semana en curso


def test_next_session_cycles_from_last_finished_day(client, monkeypatch):
    api, _, student, squat, _, add, finish = setup(client, monkeypatch)
    assert get(api, student).json()["next_session"]["day_name"] == "Día 1"
    add(squat, 1, 40, reps="8")
    finish(1)
    session = get(api, student).json()["next_session"]
    [exercise] = session["exercises"]
    assert session["day_name"] == "Día 1"  # rutina de un solo día
    assert exercise["name"] == "Sentadilla" and exercise["last"] == {"weight": 40.0, "reps": 8}
    assert (exercise["target_weight"], exercise["sets"], exercise["reps"]) == (10.0, 3, "8")
    assert exercise["adjusted_by_trainer"] is False and session["trainer_feedback"] is None


def test_empty_state_validation_authorization_and_isolation(client, monkeypatch):
    api, trainer, student, squat, _, add, _ = setup(client, monkeypatch)
    empty = get(api, student).json()
    assert empty["has_sessions"] is False and empty["exercises"] == [] and empty["records"] == []
    add(squat, 1, 50)  # una sola sesión
    [only] = get(api, student).json()["exercises"]
    assert only["message_key"] == "few_data"

    assert get(api, student, period="2w").status_code == 422
    assert api.get(PATH, headers=trainer).status_code == 403
    assert api.get(PATH).status_code == 401
    other = register_and_login(api, "other@example.com", "STUDENT")
    unlinked = get(api, other).json()  # no ve las series de otro alumno y sin vínculo no hay constancia ni próxima sesión
    assert unlinked["has_sessions"] is False and unlinked["consistency"] == [] and unlinked["next_session"] is None


def test_next_session_shows_trainer_adjustment_and_feedback(client, monkeypatch):
    from backend.tests.test_us26_session_adjustment_api import adjustment_path, blocks
    from backend.tests.test_us26_session_adjustment_api import setup as setup_us26
    from backend.tests.test_workout_session_api import TEMPLATES_PATH

    api, _, trainer, student, exercise_id, relationship_id, _, session_id = setup_us26(client, monkeypatch)
    saved = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id), "note": "Subí la carga"})
    assert saved.status_code == 200
    feedback = api.put(
        f"{TEMPLATES_PATH}/assignments/{relationship_id}/workout-sessions/{session_id}/effort-feedback",
        headers=trainer, json={"category": "MORE_EFFORT", "comment": "Podés exigirte más."},
    )
    assert feedback.status_code == 200

    session = get(api, student).json()["next_session"]
    [exercise] = session["exercises"]
    assert session["trainer_feedback"] == "Podés exigirte más."
    assert exercise["adjusted_by_trainer"] is True and exercise["trainer_note"] == "Subí la carga"
    assert (exercise["target_weight"], exercise["sets"], exercise["reps"]) == (12.5, 4, "6")
    assert exercise["last"] == {"weight": 10.0, "reps": 8}  # log_set(..., peso 10)
