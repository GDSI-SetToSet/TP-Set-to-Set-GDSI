from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from backend.src.models.body_map_report import BodyMapPainReport, BodyMapPainReportZone
from backend.src.models.exercise_replacement_log import ExerciseReplacementLog
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.session_adjustment import SessionAdjustment
from backend.src.models.student_routine import RoutineChangeLog
from backend.src.models.workout_log import WorkoutSession
from backend.tests.test_us22_daily_routines_api import (
    SESSIONS_PATH,
    fixed_clock,
    log_set,
)
from backend.tests.test_workout_session_api import (
    ASSIGNED_PATH,
    create_assigned_routine,
    register_and_login,
)

ADJUSTMENTS_PATH = "/api/v1/students/me/routine-adjustments"


def adjustment_path(session_id: str) -> str:
    return f"/api/v1/trainers/me/sessions/{session_id}/adjustment"


def blocks(
    exercise_id: str, sets: int = 4, reps: str = "6", weight: float | None = 12.5, rest: int = 90
) -> list[dict]:
    return [
        {
            "name": "Principal",
            "exercises": [
                {"exercise_id": exercise_id, "sets": sets, "reps": reps, "rest_seconds": rest, "target_weight_kg": weight}
            ],
        }
    ]


def create_exercise(api, trainer, name: str, **overrides) -> str:
    response = api.post(
        "/api/v1/exercises",
        headers=trainer,
        json={
            "name": name,
            "description": "Ejercicio",
            "category": "FUERZA",
            "target_muscle_group": "Piernas",
            "equipment_needed": "Mancuerna",
            **overrides,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def start(api, student) -> dict:
    response = api.post(SESSIONS_PATH, headers=student, json={"day_name": "Día 1"})
    assert response.status_code == 201
    return response.json()


def finish(api, student, session_id: str, rpe: int | None = None) -> None:
    body = {"rpe": rpe} if rpe is not None else None
    assert api.post(f"{SESSIONS_PATH}/{session_id}/finish", headers=student, json=body).status_code == 200


def planned_sets(api, student) -> int:
    routine = api.get(ASSIGNED_PATH, headers=student).json()
    return routine["days"][0]["blocks"][0]["exercises"][0]["sets"]


def setup(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    exercise_id, relationship_id = create_assigned_routine(api, sessions, trainer, "student@example.com")
    clock = fixed_clock(monkeypatch, datetime(2026, 11, 12, 13, 0, tzinfo=UTC))
    session = start(api, student)
    clock["now"] += timedelta(minutes=5)
    log_set(api, student, exercise_id, session["id"], 1, 10, 30)
    clock["now"] += timedelta(minutes=30)
    finish(api, student, session["id"], rpe=9)
    clock["now"] += timedelta(hours=2)
    return api, sessions, trainer, student, exercise_id, relationship_id, clock, session["id"]


def test_context_shows_the_session_reports_and_the_day_to_adjust(client, monkeypatch):
    api, sessions, trainer, _, exercise_id, relationship_id, _, session_id = setup(client, monkeypatch)
    with sessions() as db:
        stored = db.get(WorkoutSession, session_id)
        report = BodyMapPainReport(
            student_id=stored.student_id,
            relationship_id=relationship_id,
            session_id=session_id,
            exercise_id=exercise_id,
            context="IN_EXERCISE",
            action_taken="NONE",
            created_at=datetime(2026, 11, 12, 13, 10),
        )
        report.zones.append(BodyMapPainReportZone(zone="Knee", intensity="PAIN", created_at=report.created_at))
        report.zones.append(BodyMapPainReportZone(zone="Neck", intensity="NORMAL", created_at=report.created_at))
        db.add(report)
        db.add(
            ExerciseReplacementLog(
                student_id=stored.student_id,
                routine_id=stored.routine_id,
                day_name="Día 1",
                session_date=date(2026, 11, 12),
                original_exercise_id=exercise_id,
                replacement_exercise_id=None,
                updated_at=datetime(2026, 11, 12, 13, 15),
            )
        )
        db.commit()

    response = api.get(adjustment_path(session_id), headers=trainer)

    assert response.status_code == 200
    body = response.json()
    assert body["day_name"] == "Día 1"
    assert body["rpe"] == 9
    assert body["can_adjust"] is True
    assert body["blocked_reason"] is None
    assert body["current_adjustment"] is None
    assert body["logged_exercises"][0]["sets"] == [{"set_number": 1, "reps_completed": "8", "weight_kg": 10.0}]
    assert body["pain_zones"] == [
        {"zone": "Knee", "zone_label": "Rodilla", "intensity": "PAIN", "exercise_name": "Sentadilla", "context": "IN_EXERCISE"}
    ]
    assert body["replacement_requests"] == [
        {"original_exercise_id": exercise_id, "original_exercise_name": "Sentadilla", "replacement_exercise_name": None}
    ]
    [entry] = body["blocks"][0]["exercises"]
    assert entry == {
        "exercise_id": exercise_id,
        "exercise_name": "Sentadilla",
        "sets": 3,
        "reps": "8",
        "rest_seconds": 60,
        "target_weight_kg": 10.0,
    }


def test_adjustment_is_applied_and_marked_until_the_student_trains_that_day(client, monkeypatch):
    api, sessions, trainer, student, exercise_id, _, clock, session_id = setup(client, monkeypatch)

    response = api.put(
        adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id), "note": "  Subí la carga  "}
    )

    assert response.status_code == 200
    saved = response.json()
    assert saved["status"] == "APPLIED"
    assert saved["note"] == "Subí la carga"
    assert saved["changed_exercise_ids"] == [exercise_id]
    assert planned_sets(api, student) == 4
    [notice] = api.get(ADJUSTMENTS_PATH, headers=student).json()
    assert notice["day_name"] == "Día 1"
    assert notice["note"] == "Subí la carga"
    assert notice["exercise_ids"] == [exercise_id]
    context = api.get(adjustment_path(session_id), headers=trainer).json()
    assert context["current_adjustment"]["status"] == "APPLIED"
    assert context["blocks"][0]["exercises"][0]["sets"] == 4
    with sessions() as db:
        [change] = db.scalars(select(RoutineChangeLog)).all()
        assert change.changes["session_adjustment_id"] == saved["id"]
        assert change.changes["modified"][0]["after"]["sets"] == 4

    clock["now"] += timedelta(days=2)
    next_session = start(api, student)
    assert api.get(ADJUSTMENTS_PATH, headers=student).json()[0]["day_name"] == "Día 1"  # en curso: sigue marcado
    clock["now"] += timedelta(minutes=40)
    finish(api, student, next_session["id"])

    assert api.get(ADJUSTMENTS_PATH, headers=student).json() == []
    assert api.get(adjustment_path(session_id), headers=trainer).json()["current_adjustment"] is None
    assert planned_sets(api, student) == 4  # el ajuste es persistente


def test_adjustment_waits_for_the_session_in_progress_and_applies_when_it_finishes(client, monkeypatch):
    api, _, trainer, student, exercise_id, _, clock, session_id = setup(client, monkeypatch)
    in_progress = start(api, student)

    response = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id)})

    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"
    assert response.json()["applied_at"] is None
    assert planned_sets(api, student) == 3
    assert api.get(ADJUSTMENTS_PATH, headers=student).json() == []
    context = api.get(adjustment_path(session_id), headers=trainer).json()
    assert context["current_adjustment"]["status"] == "PENDING"
    assert context["blocks"][0]["exercises"][0]["sets"] == 4  # se edita sobre lo pendiente
    log_set(api, student, exercise_id, in_progress["id"], 1, 10, 30)  # la sesión en curso no se altera

    clock["now"] += timedelta(minutes=30)
    finish(api, student, in_progress["id"])

    assert planned_sets(api, student) == 4
    assert api.get(ADJUSTMENTS_PATH, headers=student).json()[0]["exercise_ids"] == [exercise_id]


def test_pending_adjustment_is_applied_when_an_abandoned_session_is_replaced_by_a_new_one(client, monkeypatch):
    api, _, trainer, student, exercise_id, _, clock, session_id = setup(client, monkeypatch)
    start(api, student)  # queda abandonada
    first = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id, sets=5)})
    second = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id, sets=4)})
    assert first.json()["status"] == second.json()["status"] == "PENDING"

    clock["now"] += timedelta(days=1)
    start(api, student)

    assert planned_sets(api, student) == 4  # el último ajuste reemplazó al anterior
    assert len(api.get(ADJUSTMENTS_PATH, headers=student).json()) == 1


def test_replacing_with_a_contraindicated_exercise_is_blocked_with_a_warning(client, monkeypatch):
    api, sessions, trainer, student, _, _, _, session_id = setup(client, monkeypatch)
    risky = create_exercise(api, trainer, "Prensa", contraindicated_zones=["Knee"])
    with sessions() as db:
        stored = db.get(WorkoutSession, session_id)
        db.add(ProtectedZone(student_id=stored.student_id, body_area="Knee", created_at=datetime.now(UTC)))
        db.commit()

    response = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(risky)})

    assert response.status_code == 422
    [error] = response.json()["errors"]
    assert error["field"].endswith("blocks.0.exercises.0.exercise_id")
    assert "contraindicado" in error["message"]
    assert planned_sets(api, student) == 3


def test_replacing_an_exercise_marks_the_new_one(client, monkeypatch):
    api, _, trainer, student, _, _, _, session_id = setup(client, monkeypatch)
    lunge = create_exercise(api, trainer, "Estocada")

    saved = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(lunge, sets=3, reps="8", weight=10, rest=60)})

    assert saved.status_code == 200
    assert saved.json()["changed_exercise_ids"] == [lunge]
    routine = api.get(ASSIGNED_PATH, headers=student).json()
    assert routine["days"][0]["blocks"][0]["exercises"][0]["exercise"]["name"] == "Estocada"


def test_adjustment_rules_and_privacy(client, monkeypatch):
    api, sessions, trainer, student, exercise_id, _, _, session_id = setup(client, monkeypatch)
    other_trainer = register_and_login(api, "other@example.com", "TRAINER")
    in_progress = start(api, student)

    assert api.get(adjustment_path(in_progress["id"]), headers=trainer).status_code == 409
    assert api.put(adjustment_path(in_progress["id"]), headers=trainer, json={"blocks": blocks(exercise_id)}).status_code == 409
    assert api.get(adjustment_path(session_id), headers=other_trainer).status_code == 404
    assert api.get(adjustment_path("no-existe"), headers=trainer).status_code == 404
    assert api.get(adjustment_path(session_id), headers=student).status_code in (403, 404)
    assert api.get(adjustment_path(session_id)).status_code == 401

    unchanged = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id, 3, "8", 10, 60)})
    assert unchanged.status_code == 422
    assert "No hiciste cambios" in unchanged.json()["detail"]
    assert api.put(adjustment_path(session_id), headers=trainer, json={"blocks": [], "note": "x"}).status_code == 422
    assert api.put(
        adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id), "note": "x" * 501}
    ).status_code == 422

    student_id = api.get("/api/v1/routine-templates/assignments", headers=trainer).json()[0]["student_id"]
    base = f"/api/v1/trainers/me/students/{student_id}/routine"
    current = api.get(base, headers=trainer).json()
    draft = {
        "name": "Rutina de prueba",
        "duration_weeks": 6,
        "intensity": "MEDIA",
        "has_no_materials_alternative": False,
        "days": [{"name": "Día 1", "blocks": blocks(exercise_id, 3, "8", 10, 60)}],
        "draft_version": current["draft_version"],
    }
    assert api.put(f"{base}/draft", headers=trainer, json=draft).status_code == 200

    context = api.get(adjustment_path(session_id), headers=trainer).json()
    assert context["can_adjust"] is False
    assert "borrador" in context["blocked_reason"]
    blocked = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id)})
    assert blocked.status_code == 409

    with sessions() as db:
        assert db.scalars(select(SessionAdjustment)).all() == []


def test_student_without_active_relationship_sees_no_adjustments(client):
    api, _ = client
    student = register_and_login(api, "lonely@example.com", "STUDENT")
    trainer = register_and_login(api, "trainer-only@example.com", "TRAINER")

    assert api.get(ADJUSTMENTS_PATH, headers=student).json() == []
    assert api.get(ADJUSTMENTS_PATH, headers=trainer).status_code in (403, 404)
