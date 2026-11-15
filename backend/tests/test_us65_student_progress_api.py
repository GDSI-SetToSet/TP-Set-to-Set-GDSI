from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from backend.src.models.exercise import Exercise
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.workout_log import WorkoutSetLog
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
        student_id = db.get(TrainingRelationship, relationship_id).student_id
        press = Exercise(
            name="Press banca", description="x", category="FUERZA", target_muscle_group="Pecho",
            equipment_needed="Barra", trainer_id=db.get(Exercise, squat).trainer_id,
            created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
        )
        db.add(press)
        db.commit()
        press_id = press.id

    def add(exercise_id, weeks_ago, weight, reps="8", set_number=1, day_offset=0):
        moment = (NOW - weeks_ago * WEEK + timedelta(days=day_offset)).replace(tzinfo=None)
        with sessions() as db:
            db.add(WorkoutSetLog(
                student_id=student_id, relationship_id=relationship_id, routine_id="r", day_name="Día 1",
                exercise_id=exercise_id, exercise_name="x", set_number=set_number, reps_completed=reps,
                weight_kg=Decimal(str(weight)) if weight is not None else None, recorded_at=moment,
            ))
            db.commit()

    return api, trainer, student, squat, press_id, add


def get(api, student, **params):
    return api.get(PATH, headers=student, params=params)


def test_load_per_exercise_and_default_12_week_range(client, monkeypatch):
    api, _, student, squat, _, add = setup(client, monkeypatch)
    add(squat, 20, 50)  # fuera del rango por defecto (12 semanas)
    add(squat, 3, 60)
    add(squat, 1, 70, reps="5")
    body = get(api, student).json()

    assert body["range"] == {"from": "2026-08-24", "to": "2026-11-14", "is_default": True}
    assert len(body["weekly_volume"]) == 12
    [exercise] = body["exercises"]
    assert exercise["name"] == "Sentadilla" and exercise["has_trend"] is True
    assert [(p["weight_kg"], p["reps"], p["is_pr"]) for p in exercise["points"]] == [(60.0, "8", True), (70.0, "5", True)]  # 60 supera los 50 previos fuera del rango
    assert body["has_data"] is True and body["muscle_groups"] == ["Piernas"]


def test_weekly_volume_with_empty_weeks_and_comparison(client, monkeypatch):
    api, _, student, squat, _, add = setup(client, monkeypatch)
    add(squat, 2, 50, reps="10")  # 500
    add(squat, 2, 50, reps="10", set_number=2)  # 500
    add(squat, 0, 100, reps="5", day_offset=-3)  # semana en curso: 500
    add(squat, 0, 40, reps="al fallo", set_number=2, day_offset=-3)  # reps no numéricas: no suma al volumen
    body = get(api, student, **{"from": "2026-10-19", "to": "2026-11-14"}).json()

    volumes = [w["volume_kg"] for w in body["weekly_volume"]]
    assert volumes == [0.0, 1000.0, 0.0, 500.0]  # la semana sin series queda en 0
    assert [w["is_partial"] for w in body["weekly_volume"]] == [False] * 3 + [True]
    assert body["week_comparison"] == {
        "current_volume_kg": 500.0, "previous_volume_kg": 0.0, "delta_vs_previous_pct": None, "previous_avg_kg": 333.33,
    }
    add(squat, 1, 25, reps="10")  # 250 la semana previa
    comparison = get(api, student, **{"from": "2026-10-19", "to": "2026-11-14"}).json()["week_comparison"]
    assert comparison["previous_volume_kg"] == 250.0 and comparison["delta_vs_previous_pct"] == 100.0


def test_personal_records_are_strict_chronological_and_ignore_reps(client, monkeypatch):
    api, _, student, squat, press, add = setup(client, monkeypatch)
    add(squat, 4, 60, reps="al fallo")  # PR inicial aunque las reps no sean numéricas
    add(squat, 3, 60)  # igual al máximo previo: no es PR
    add(squat, 2, 70, reps="1")  # PR con 1 repetición
    add(squat, 1, 65)  # inferior: no es PR
    add(press, 1, 40)
    body = get(api, student).json()

    records = body["personal_records"]
    assert [(r["exercise_name"], r["weight_kg"], r["previous_weight_kg"], r["is_initial"]) for r in records] == [
        ("Sentadilla", 60.0, None, True), ("Sentadilla", 70.0, 60.0, False), ("Press banca", 40.0, None, True),
    ]
    assert [r["achieved_at"] for r in records] == sorted(r["achieved_at"] for r in records)


def test_same_session_tie_is_broken_by_set_number(client, monkeypatch):
    api, _, student, squat, _, add = setup(client, monkeypatch)
    add(squat, 1, 50, set_number=1)
    add(squat, 1, 50, set_number=2)  # mismo instante y mismo peso: no es PR
    add(squat, 1, 55, set_number=3)
    records = get(api, student).json()["personal_records"]
    assert [(r["weight_kg"], r["is_initial"]) for r in records] == [(50.0, True), (55.0, False)]


def test_filters_by_exercise_muscle_group_and_dates_keep_prior_max(client, monkeypatch):
    api, _, student, squat, press, add = setup(client, monkeypatch)
    add(squat, 8, 80)
    add(squat, 1, 70)  # inferior al máximo previo fuera del rango: no es PR aunque sea el primero del rango
    add(press, 1, 40)

    by_exercise = get(api, student, exercise_id=press).json()
    assert [e["name"] for e in by_exercise["exercises"]] == ["Press banca"]
    assert [r["exercise_name"] for r in by_exercise["personal_records"]] == ["Press banca"]
    assert [e["name"] for e in get(api, student, muscle_group="Piernas").json()["exercises"]] == ["Sentadilla"]
    assert get(api, student, exercise_id=press, muscle_group="Piernas").json()["has_data"] is False

    ranged = get(api, student, **{"from": "2026-11-02", "to": "2026-11-14"}).json()
    assert [r["exercise_name"] for r in ranged["personal_records"]] == ["Press banca"]
    assert ranged["muscle_groups"] == ["Pecho", "Piernas"]  # las opciones del filtro no dependen del rango


def test_single_point_has_no_trend_and_empty_state(client, monkeypatch):
    api, _, student, squat, _, add = setup(client, monkeypatch)
    empty = get(api, student).json()
    assert empty["has_data"] is False and empty["exercises"] == [] and empty["personal_records"] == []
    assert all(w["volume_kg"] == 0 for w in empty["weekly_volume"])
    add(squat, 1, 50)
    add(squat, 1, 0)  # sin peso: se ignora
    add(squat, 1, None)
    [exercise] = get(api, student).json()["exercises"]
    assert exercise["has_trend"] is False and len(exercise["points"]) == 1


def test_validation_authorization_and_isolation(client, monkeypatch):
    api, trainer, student, squat, _, add = setup(client, monkeypatch)
    add(squat, 1, 50)

    inverted = get(api, student, **{"from": "2026-11-14", "to": "2026-11-01"})
    assert inverted.status_code == 422 and inverted.headers["content-type"].startswith("application/problem+json")
    assert inverted.json()["errors"][0]["field"] == "from"
    malformed = get(api, student, **{"from": "no-es-fecha"})
    assert malformed.status_code == 422 and malformed.headers["content-type"].startswith("application/problem+json")

    assert api.get(PATH, headers=trainer).status_code == 403
    assert api.get(PATH).status_code == 401
    other = register_and_login(api, "other@example.com", "STUDENT")
    assert get(api, other).json()["has_data"] is False  # no ve las series de otro alumno
    assert date.fromisoformat(get(api, student).json()["range"]["to"]) == NOW.date()
