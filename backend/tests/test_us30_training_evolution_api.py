from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.workout_log import WorkoutSession
from backend.src.services.training_evolution_service import classify, effort_message
from backend.tests.test_us22_daily_routines_api import (
    SESSIONS_PATH,
    fixed_clock,
    log_set,
)
from backend.tests.test_workout_session_api import (
    create_assigned_routine,
    register_and_login,
)

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)  # sábado; la semana en curso empieza el lunes 9/11
MONDAY = date(2026, 11, 9)
WEEK = timedelta(weeks=1)


# ---- clasificación (pura) ----

def hist(*items):
    return [(MONDAY - timedelta(weeks=weeks_ago), (weight, reps)) for weeks_ago, weight, reps in items]


def test_classify_covers_every_status_in_order():
    assert classify(hist((1, 20, 8)), "max_weight", MONDAY)[0] == "few_data"
    assert classify(hist((3, 20, 8), (1, 25, 8)), "max_weight", MONDAY)[0] == "progressing"
    assert classify(hist((3, 20, 8), (2, 20, 8), (1, 20, 8)), "max_weight", MONDAY)[0] == "stalled"
    assert classify(hist((6, 20, 8), (5, 20, 8)), "max_weight", MONDAY)[0] == "unchanged"  # viejo y sin 3 sesiones en la ventana
    assert classify(hist((3, 30, 8), (2, 30, 8), (1, 20, 8)), "max_weight", MONDAY)[0] == "declined"  # ≥ 10 % menos


def test_same_weight_with_more_reps_is_an_improvement_and_bodyweight_uses_reps():
    assert classify(hist((3, 20, 8), (1, 20, 10)), "max_weight", MONDAY)[0] == "progressing"
    assert classify(hist((3, 0, 10), (1, 0, 12)), "max_reps", MONDAY)[0] == "progressing"
    assert classify(hist((3, 0, 10), (2, 0, 10), (1, 0, 8)), "max_reps", MONDAY)[0] == "declined"


@pytest.mark.parametrize(
    ("excessive", "load_up", "trend", "avg", "expected"),
    [
        (True, True, "stable", 7.0, "excessive_effort"),
        (False, False, "rising", 7.0, "fatigue"),
        (False, True, "stable", 5.0, "room_for_more"),
        (False, False, "stable", 5.5, "room_for_more"),
        (False, True, "rising", 7.0, "progressing_effort_rising"),
        (False, True, "falling", 7.0, "progressing_with_margin"),
        (False, False, "stable", 7.0, None),
        (False, True, None, None, None),
    ],
)
def test_effort_message_precedence(excessive, load_up, trend, avg, expected):
    assert effort_message(excessive, load_up, trend, avg) == expected


# ---- API ----

def evolution(api, trainer, student_id: str, **params):
    return api.get(f"/api/v1/trainers/me/students/{student_id}/evolution", headers=trainer, params=params)


def run_session(api, student, clock, exercise_id: str, weights: list[float], rpe: int | None = 7) -> str:
    session = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    for number, weight in enumerate(weights, start=1):
        log_set(api, student, exercise_id, session["id"], number, weight, 30)
    clock["now"] += timedelta(minutes=30)
    assert api.post(f"{SESSIONS_PATH}/{session['id']}/finish", headers=student, json={"rpe": rpe}).status_code == 200
    return session["id"]


def setup(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")
    clock = fixed_clock(monkeypatch, NOW - 12 * WEEK)
    with sessions() as db:  # la rutina de la prueba tiene 1 día por semana, asignada hace mucho
        db.scalars(select(TrainingRelationship)).first().routine_assigned_at = NOW - 30 * WEEK
        db.commit()
    return api, sessions, trainer, student, exercise_id, clock


def at(clock, weeks_ago: int, day_offset: int = 0):
    clock["now"] = NOW - weeks_ago * WEEK + timedelta(days=day_offset)


def student_id_of(sessions) -> str:
    with sessions() as db:
        return db.scalars(select(WorkoutSession)).first().student_id


def test_progression_per_exercise_with_partial_week_excluded_from_status(client, monkeypatch):
    api, sessions, trainer, student, ex, clock = setup(client, monkeypatch)
    for weeks_ago, weight in ((3, 10), (2, 15), (1, 20)):
        at(clock, weeks_ago)
        run_session(api, student, clock, ex, [weight])
    at(clock, 0, -3)  # esta semana (miércoles 11/11): 50 kg, pero la semana en curso no cuenta para el estado
    run_session(api, student, clock, ex, [50])
    clock["now"] = NOW
    sid = student_id_of(sessions)

    body = evolution(api, trainer, sid, group_by="session").json()

    [exercise] = body["exercises"]
    assert exercise["name"] == "Sentadilla" and exercise["muscle_group"] == "Piernas"
    assert exercise["status"] == "progressing" and exercise["metric"] == "max_weight"
    assert exercise["start"] == {"weight": 10.0, "reps": 8} and exercise["current"] == {"weight": 20.0, "reps": 8}
    assert exercise["change_pct"] == 100.0
    # US-65 FR-001a / AUD-08: primera sesión es línea base (False) y cada mejora posterior
    # que supera la marca acumulada preserva su marcador de PR histórico en evolución.
    assert exercise["last_improvement"]["is_pr"] is True
    assert [p["is_pr"] for p in exercise["points"]] == [False, True, True, True]
    assert [p["weight"] for p in exercise["points"]] == [10.0, 15.0, 20.0, 50.0]
    assert [p["is_partial"] for p in exercise["points"]] == [False, False, False, True]
    assert exercise["points"][0]["target_weight"] == 10.0 and exercise["points"][0]["rpe"] == 7
    assert body["summary"]["progress"] == {"improving": 1, "with_data": 1, "status": "green"}


def test_week_grouping_takes_the_best_set_of_each_week(client, monkeypatch):
    api, sessions, trainer, student, ex, clock = setup(client, monkeypatch)
    at(clock, 2)
    run_session(api, student, clock, ex, [10, 15])
    at(clock, 1)
    run_session(api, student, clock, ex, [20])
    clock["now"] = NOW

    points = evolution(api, trainer, student_id_of(sessions)).json()["exercises"][0]["points"]

    assert [(p["period_start"], p["period_end"], p["weight"]) for p in points] == [
        ("2026-10-26", "2026-11-01", 15.0),
        ("2026-11-02", "2026-11-08", 20.0),
    ]


def test_single_session_is_few_data_and_privacy(client, monkeypatch):
    api, sessions, trainer, student, ex, clock = setup(client, monkeypatch)
    at(clock, 1)
    run_session(api, student, clock, ex, [20])
    clock["now"] = NOW
    sid = student_id_of(sessions)

    body = evolution(api, trainer, sid).json()
    assert body["exercises"][0]["status"] == "few_data"
    assert body["summary"]["progress"] == {"improving": 0, "with_data": 0, "status": None}

    other = register_and_login(api, "other@example.com", "TRAINER")
    assert evolution(api, other, sid).status_code == 404


def test_adherence_counts_complete_weeks_only_and_flags_missed_weeks(client, monkeypatch):
    api, sessions, trainer, student, ex, clock = setup(client, monkeypatch)
    at(clock, 3)
    run_session(api, student, clock, ex, [10, 10, 10])  # semana del 19/10, con las 3 series programadas
    at(clock, 0, -3)
    run_session(api, student, clock, ex, [10, 10, 10])  # semana en curso: no entra en el porcentaje
    clock["now"] = NOW

    body = evolution(api, trainer, student_id_of(sessions), period="4w").json()

    weeks = {w["period_start"]: w for w in body["adherence"]}
    assert len(weeks) == 4 and weeks["2026-11-09"]["is_partial"] is True
    assert (weeks["2026-10-19"]["scheduled"], weeks["2026-10-19"]["completed"]) == (1, 1)
    assert weeks["2026-10-26"]["completed"] == 0
    assert body["summary"]["adherence"]["completed_sessions"] == 1
    assert body["summary"]["adherence"]["scheduled_sessions"] == 3  # 3 semanas completas
    assert body["summary"]["adherence"]["pct"] == 33 and body["summary"]["adherence"]["status"] == "red"
    assert [item["type"] for item in body["to_review"]] == ["week_without_training", "week_without_training"]
    assert body["summary"]["to_review"] == {"count": 2, "status": "yellow"}


def test_sets_completion_and_most_skipped_exercises(client, monkeypatch):
    api, sessions, trainer, student, ex, clock = setup(client, monkeypatch)
    at(clock, 2)
    run_session(api, student, clock, ex, [10])  # 1 de 3 series programadas
    at(clock, 1)
    run_session(api, student, clock, ex, [10, 10])  # 2 de 3
    clock["now"] = NOW

    body = evolution(api, trainer, student_id_of(sessions)).json()

    assert body["summary"]["adherence"]["sets_completion_pct"] == 50
    assert body["most_skipped"] == [
        {"exercise_id": ex, "name": "Sentadilla", "completion_pct": 50, "skip_count": 0, "main_reason": None}
    ]
    assert "exercise_skipped" in [item["type"] for item in body["to_review"]]


def test_rpe_points_keep_gaps_and_summary_trend(client, monkeypatch):
    api, sessions, trainer, student, ex, clock = setup(client, monkeypatch)
    for weeks_ago, rpe in ((5, 6), (4, None), (3, 7), (2, 7), (1, 9)):
        at(clock, weeks_ago)
        run_session(api, student, clock, ex, [10], rpe=rpe)
    clock["now"] = NOW

    body = evolution(api, trainer, student_id_of(sessions), group_by="session").json()

    assert [p["rpe"] for p in body["rpe"]] == [6, None, 7, 7, 9]
    assert [p["has_report"] for p in body["rpe"]] == [True, False, True, True, True]
    assert body["summary"]["effort"]["avg_rpe_last_4"] == 7.2
    assert body["summary"]["effort"]["message_key"] == "excessive_effort"
    assert body["summary"]["effort"]["status"] == "yellow"
    assert any(item["type"] == "excessive_effort" for item in body["to_review"])


def test_muscle_group_filter_and_options(client, monkeypatch):
    api, sessions, trainer, student, ex, clock = setup(client, monkeypatch)
    at(clock, 2)
    run_session(api, student, clock, ex, [10])
    clock["now"] = NOW
    sid = student_id_of(sessions)

    legs = evolution(api, trainer, sid, muscle_group="Piernas").json()
    chest = evolution(api, trainer, sid, muscle_group="Pecho").json()

    assert legs["muscle_groups"] == ["Piernas"] and len(legs["exercises"]) == 1
    assert chest["exercises"] == [] and chest["sets_by_muscle_group"] == []
    assert legs["sets_by_muscle_group"][0]["muscle_group"] == "Piernas"
    assert legs["sets_by_muscle_group"][0]["avg_scheduled_per_week"] == 3.0


def test_no_sessions_and_invalid_params_and_privacy(client, monkeypatch):
    api, sessions, trainer, student, *_ = setup(client, monkeypatch)
    with sessions() as db:
        sid = db.scalars(select(TrainingRelationship)).first().student_id

    body = evolution(api, trainer, sid).json()
    assert body["has_sessions"] is False and body["exercises"] == []
    assert evolution(api, trainer, sid, group_by="muscle_group").status_code == 422
    assert evolution(api, trainer, sid, period="1y").status_code == 422
    assert evolution(api, student, sid).status_code == 403


def test_works_with_the_real_clock(client):
    # Sin fixed_clock: utc_now() devuelve fechas sin zona horaria, como en producción.
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, _ = create_assigned_routine(api, sessions, trainer, "student@example.com")
    session = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"}).json()
    log_set(api, student, exercise_id, session["id"], 1, 20, 30)
    api.post(f"{SESSIONS_PATH}/{session['id']}/finish", headers=student, json={"rpe": 7})

    for params in ({}, {"group_by": "session", "period": "all"}, {"period": "4w"}):
        response = evolution(api, trainer, student_id_of(sessions), **params)
        assert response.status_code == 200
    assert response.json()["exercises"][0]["points"][0]["is_partial"] is True
