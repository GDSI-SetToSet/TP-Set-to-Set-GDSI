from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from backend.src.models.body_map_report import BodyMapPainReport, BodyMapPainReportZone
from backend.src.models.exercise_replacement_log import ExerciseReplacementLog
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.session_adjustment import SessionAdjustment
from backend.src.models.student_routine import RoutineChangeLog
from backend.src.models.workout_log import WorkoutSession
from backend.src.services import session_adjustment_service, student_routine_service
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
    monkeypatch.setattr(session_adjustment_service, "utc_now", lambda: clock["now"])
    monkeypatch.setattr(student_routine_service, "utc_now", lambda: clock["now"])
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


def test_historical_abandoned_session_does_not_keep_new_adjustment_pending(client, monkeypatch):
    """DEF-03: una sesión antigua abandonada con finished_at=NULL no deja el ajuste nuevo en PENDING."""
    api, _, trainer, student, exercise_id, _, clock, session_id = setup(client, monkeypatch)
    # Simular sesión abandonada previa al último entrenamiento finalizado:
    abandoned_at = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    clock_backup = clock["now"]
    clock["now"] = abandoned_at
    # Insertar sesión abandonada directa previa a session_id
    with client[1]() as db:
        finished = db.get(WorkoutSession, session_id)
        db.add(
            WorkoutSession(
                student_id=finished.student_id,
                relationship_id=finished.relationship_id,
                routine_id=finished.routine_id,
                day_name="Día 1",
                modality="GYM",
                started_at=abandoned_at,
                finished_at=None,
            )
        )
        db.commit()
    clock["now"] = clock_backup

    saved = api.put(adjustment_path(session_id), headers=trainer, json={"blocks": blocks(exercise_id, sets=5)})
    assert saved.status_code == 200
    assert saved.json()["status"] == "APPLIED"
    assert planned_sets(api, student) == 5


def test_successive_adjustments_and_note_edits_preserve_changed_exercise_ids(client, monkeypatch):
    """DEF-04: editar la nota o hacer ajustes sucesivos conserva changed_exercise_ids acumulados."""
    api, _, trainer, student, ex_a, _relationship_id, _, _ = setup(client, monkeypatch)
    ex_b = create_exercise(api, trainer, "Prensa")

    # Armar rutina con A y B el Día 1
    student_id = api.get("/api/v1/routine-templates/assignments", headers=trainer).json()[0]["student_id"]
    base = f"/api/v1/trainers/me/students/{student_id}/routine"
    current = api.get(base, headers=trainer).json()
    two_ex_blocks = [
        {
            "name": "Principal",
            "exercises": [
                {"exercise_id": ex_a, "sets": 3, "reps": "8", "rest_seconds": 60, "target_weight_kg": 10},
                {"exercise_id": ex_b, "sets": 3, "reps": "10", "rest_seconds": 60, "target_weight_kg": 20},
            ],
        }
    ]
    assert api.put(
        f"{base}/draft",
        headers=trainer,
        json={
            "name": "Rutina de prueba",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "has_no_materials_alternative": False,
            "days": [{"name": "Día 1", "blocks": two_ex_blocks}],
            "draft_version": current["draft_version"],
        },
    ).status_code == 200
    assert api.post(f"{base}/draft/confirm", headers=trainer).status_code == 200

    s1 = start(api, student)
    log_set(api, student, ex_a, s1["id"], 1, 10, 30)
    finish(api, student, s1["id"], rpe=7)

    # 1er ajuste: cambia solo ex_a
    first_blocks = [
        {
            "name": "Principal",
            "exercises": [
                {"exercise_id": ex_a, "sets": 4, "reps": "8", "rest_seconds": 60, "target_weight_kg": 12.5},
                {"exercise_id": ex_b, "sets": 3, "reps": "10", "rest_seconds": 60, "target_weight_kg": 20},
            ],
        }
    ]
    r1 = api.put(adjustment_path(s1["id"]), headers=trainer, json={"blocks": first_blocks, "note": "Nota 1"})
    assert r1.status_code == 200
    assert r1.json()["changed_exercise_ids"] == [ex_a]

    # 2do ajuste: solo actualiza la nota sin volver a tocar los bloques
    r2 = api.put(adjustment_path(s1["id"]), headers=trainer, json={"blocks": first_blocks, "note": "Nota editada"})
    assert r2.status_code == 200
    assert r2.json()["note"] == "Nota editada"
    assert r2.json()["changed_exercise_ids"] == [ex_a]

    # 3er ajuste: ahora modifica también ex_b; deben mantenerse ambos ids en changed_exercise_ids
    third_blocks = [
        {
            "name": "Principal",
            "exercises": [
                {"exercise_id": ex_a, "sets": 4, "reps": "8", "rest_seconds": 60, "target_weight_kg": 12.5},
                {"exercise_id": ex_b, "sets": 4, "reps": "10", "rest_seconds": 60, "target_weight_kg": 25},
            ],
        }
    ]
    r3 = api.put(adjustment_path(s1["id"]), headers=trainer, json={"blocks": third_blocks, "note": "Nota editada"})
    assert r3.status_code == 200
    assert set(r3.json()["changed_exercise_ids"]) == {ex_a, ex_b}
    [notice] = api.get(ADJUSTMENTS_PATH, headers=student).json()
    assert set(notice["exercise_ids"]) == {ex_a, ex_b}
    assert notice["note"] == "Nota editada"


def test_contraindication_validation_only_checks_adjusted_day_and_revalidates_pending_on_apply(client, monkeypatch):
    """DEF-06: ajustar un día no se bloquea por otro día intacto y un PENDING se revalida al aplicarse."""
    api, sessions, trainer, student, safe_ex, _, clock, _ = setup(client, monkeypatch)
    knee_ex = create_exercise(api, trainer, "Prensa pesada", contraindicated_zones=["Knee"])

    # Configurar rutina de 2 días: Día 1 (safe_ex) y Día 2 (knee_ex, antes de que el alumno reporte zona Knee)
    student_id = api.get("/api/v1/routine-templates/assignments", headers=trainer).json()[0]["student_id"]
    base = f"/api/v1/trainers/me/students/{student_id}/routine"
    current = api.get(base, headers=trainer).json()
    assert api.put(
        f"{base}/draft",
        headers=trainer,
        json={
            "name": "Rutina de prueba",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "has_no_materials_alternative": False,
            "days": [
                {"name": "Día 1", "blocks": blocks(safe_ex, sets=3, reps="8", weight=10, rest=60)},
                {"name": "Día 2", "blocks": blocks(knee_ex, sets=3, reps="10", weight=20, rest=60)},
            ],
            "draft_version": current["draft_version"],
        },
    ).status_code == 200
    assert api.post(f"{base}/draft/confirm", headers=trainer).status_code == 200

    # El alumno agrega protección en rodilla ("Knee") posteriormente
    s1 = start(api, student)
    log_set(api, student, safe_ex, s1["id"], 1, 10, 30)
    finish(api, student, s1["id"], rpe=7)

    with sessions() as db:
        stored = db.get(WorkoutSession, s1["id"])
        # Primero ajustar mientras existe una sesión en curso con knee_ex (aún sin zona protegida) -> queda PENDING
        in_progress = start(api, student)
        pending_resp = api.put(adjustment_path(s1["id"]), headers=trainer, json={"blocks": blocks(knee_ex, sets=4)})
        assert pending_resp.status_code == 200
        assert pending_resp.json()["status"] == "PENDING"

        # Luego el alumno agrega Knee antes de finalizar la sesión en curso
        db.add(ProtectedZone(student_id=stored.student_id, body_area="Knee", created_at=datetime.now(UTC)))
        db.commit()

    # Al finalizar in_progress, apply_pending_adjustments debe revalidar y NO aplicar knee_ex
    clock["now"] += timedelta(minutes=25)
    finish(api, student, in_progress["id"])
    routine_after_blocked = api.get(ASSIGNED_PATH, headers=student).json()
    assert routine_after_blocked["days"][0]["blocks"][0]["exercises"][0]["exercise"]["id"] == safe_ex

    # Ahora ajustar Día 1 con otro cambio válido debe permitirse aunque Día 2 conserve knee_ex
    ok_resp = api.put(adjustment_path(s1["id"]), headers=trainer, json={"blocks": blocks(safe_ex, sets=4, weight=15)})
    assert ok_resp.status_code == 200
    assert planned_sets(api, student) == 4


def test_end_to_end_us24_and_us26_multi_session_integration(client, monkeypatch):
    """Integración completa US-24 + US-26: S1 -> ajuste -> S2 muestra histórico en S1, ajustado en S2 y S1 como previa."""
    api, _, trainer, student, ex_a, _, clock, _ = setup(client, monkeypatch)
    ex_b = create_exercise(api, trainer, "Zancada")
    clock["now"] = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)
    s1 = start(api, student)
    log_set(api, student, ex_a, s1["id"], 1, 10, 20)
    clock["now"] += timedelta(minutes=30)
    finish(api, student, s1["id"], rpe=8)

    # Entrenador compara S1 y luego ajusta próxima sesión sustituyendo A por B
    comp1 = api.get(f"/api/v1/trainers/me/sessions/{s1['id']}/comparison", headers=trainer).json()
    assert comp1["exercises"][0]["planned"] == {"sets": 3, "reps": "8", "target_weight_kg": 10.0}

    adj = api.put(
        adjustment_path(s1["id"]),
        headers=trainer,
        json={"blocks": blocks(ex_b, sets=4, reps="12", weight=14, rest=60), "note": "Cuidar técnica"},
    )
    assert adj.status_code == 200
    assert adj.json()["status"] == "APPLIED"

    # S1 debe conservar su plan histórico original (ex_a, 3x8 @ 10kg)
    comp1_after = api.get(f"/api/v1/trainers/me/sessions/{s1['id']}/comparison", headers=trainer).json()
    assert comp1_after["exercises"][0]["exercise_id"] == ex_a
    assert comp1_after["exercises"][0]["planned"] == {"sets": 3, "reps": "8", "target_weight_kg": 10.0}

    # Alumno inicia y completa S2 con el plan ajustado
    clock["now"] += timedelta(days=2)
    s2 = start(api, student)
    assert api.get(ADJUSTMENTS_PATH, headers=student).json()[0]["note"] == "Cuidar técnica"
    log_set(api, student, ex_b, s2["id"], 1, 14, 25)
    clock["now"] += timedelta(minutes=35)
    finish(api, student, s2["id"], rpe=7)

    assert api.get(ADJUSTMENTS_PATH, headers=student).json() == []
    comp2 = api.get(f"/api/v1/trainers/me/sessions/{s2['id']}/comparison", headers=trainer).json()
    assert comp2["previous_session"]["id"] == s1["id"]
    planned_row = next(e for e in comp2["exercises"] if e["exercise_id"] == ex_b)
    assert planned_row["planned"] == {"sets": 4, "reps": "12", "target_weight_kg": 14.0}
    assert planned_row["performed"]["sets_completed"] == 1
    prev_row = next(e for e in comp2["exercises"] if e["exercise_id"] == ex_a)
    assert prev_row["previous"] is not None
    assert prev_row["previous"]["max_weight_kg"] == 10.0


def test_concurrent_save_adjustment_and_finish_session_sqlite_file(tmp_path):
    """DEF-12: carreras reales en SQLite archivo entre save_adjustment y finish/start nunca dejan ajustes huérfanos ni fallan."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from decimal import Decimal

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    from backend.src.core.database import Base
    from backend.src.core.security import hash_password
    from backend.src.models.exercise import Exercise, VideoPlatform
    from backend.src.models.routine_template import (
        RoutineTemplate,
        RoutineTemplateBlock,
        RoutineTemplateDay,
        RoutineTemplateExercise,
        RoutineTemplateExercisePrescription,
    )
    from backend.src.models.student_profile import StudentProfile
    from backend.src.models.trainer_profile import TrainerProfile
    from backend.src.models.training_plan import TrainingPlan
    from backend.src.models.training_relationship import TrainingRelationship
    from backend.src.models.user import User, new_id
    from backend.src.schemas.routine_template import WorkoutSessionStartInput
    from backend.src.schemas.session_adjustment import AdjustmentInput
    from backend.src.services.routine_template_service import (
        finish_student_workout_session,
        start_student_workout_session,
    )

    db_file = tmp_path / "def12_concurrent.db"
    eng = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(eng, "connect")
    def _fk(dbapi_conn, _):
        c = dbapi_conn.cursor()
        c.execute("PRAGMA foreign_keys=ON")
        c.close()

    SessionLocal = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=eng)

    try:
        base_now = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)
        with SessionLocal() as db:
            tr_user = User(id=new_id(), email="tr@example.com", password_hash=hash_password("Pass123!"), role="TRAINER", created_at=base_now)
            st_user = User(id=new_id(), email="st@example.com", password_hash=hash_password("Pass123!"), role="STUDENT", created_at=base_now)
            db.add_all([tr_user, st_user])
            db.flush()
            tr = TrainerProfile(id=new_id(), user_id=tr_user.id, full_name="Coach", status="PUBLISHED", max_students=5, created_at=base_now, updated_at=base_now)
            st = StudentProfile(id=new_id(), user_id=st_user.id, first_name="Lucía", last_name="Test", status="PUBLISHED", fitness_goals=[], created_at=base_now, updated_at=base_now)
            db.add_all([tr, st])
            db.flush()
            plan = TrainingPlan(id=new_id(), trainer_id=tr.id, title="Plan", monthly_price=Decimal(100), currency="USD", is_active=True, created_at=base_now, updated_at=base_now)
            ex = Exercise(id=new_id(), trainer_id=tr.id, name="Sentadilla", description="Piernas", category="FUERZA", target_muscle_group="Piernas", equipment_needed="Barra", contraindicated_zones=[], video_platform=VideoPlatform.NONE, created_at=base_now, updated_at=base_now)
            db.add_all([plan, ex])
            db.flush()
            tpl = RoutineTemplate(
                id=new_id(), trainer_id=tr.id, name="Rutina", duration_weeks=4, intensity="MEDIA", created_at=base_now, updated_at=base_now,
                days=[RoutineTemplateDay(name="Día 1", order_index=1, blocks=[RoutineTemplateBlock(name="Principal", order_index=1, exercises=[
                    RoutineTemplateExercise(exercise_id=ex.id, order_index=1, sets=3, reps="8", rest_seconds=60, prescription=RoutineTemplateExercisePrescription(target_weight_kg=Decimal(10)))
                ])])],
            )
            db.add(tpl)
            db.flush()
            rel = TrainingRelationship(
                id=new_id(), student_id=st.id, trainer_id=tr.id, plan_id=plan.id, agreed_monthly_price=Decimal(100), agreed_currency="USD",
                status="ACTIVE", start_date=date(2026, 11, 1), initial_routine_id=tpl.id, routine_assignment_id=new_id(), routine_assigned_at=base_now,
            )
            db.add(rel)
            db.flush()
            s_finished = WorkoutSession(
                id=new_id(), student_id=st.id, relationship_id=rel.id, routine_id=tpl.id, day_name="Día 1", modality="GYM",
                started_at=base_now, finished_at=base_now + timedelta(minutes=20), rpe=8,
            )
            db.add(s_finished)
            db.commit()
            tr_user_id, st_user_id, rel_id, ex_id, fin_id = tr_user.id, st_user.id, rel.id, ex.id, s_finished.id

        # Carrera repetida: alumno finaliza sesión activa mientras entrenador guarda ajuste sobre s_finished
        for iteration in range(5):
            with SessionLocal() as db:
                st_u = db.get(User, st_user_id)
                active_sess = start_student_workout_session(db, st_u, WorkoutSessionStartInput(day_name="Día 1"))
                active_id = active_sess.id

            barrier = threading.Barrier(2)

            def _trainer_save(iteration=iteration, barrier=barrier):
                with SessionLocal() as tdb:
                    tu = tdb.get(User, tr_user_id)
                    barrier.wait(timeout=5)
                    return session_adjustment_service.save_adjustment(
                        tdb, tu, fin_id,
                        AdjustmentInput.model_validate({
                            "blocks": blocks(ex_id, sets=4 + iteration, reps="8", weight=12.5 + iteration, rest=60),
                            "note": f"Iteración {iteration}",
                        }),
                    )

            def _student_finish(active_id=active_id, barrier=barrier):
                with SessionLocal() as sdb:
                    su = sdb.get(User, st_user_id)
                    barrier.wait(timeout=5)
                    return finish_student_workout_session(sdb, su, active_id, rpe=7)

            with ThreadPoolExecutor(max_workers=2) as pool:
                f_trainer = pool.submit(_trainer_save)
                f_student = pool.submit(_student_finish)
                adj_view = f_trainer.result()
                finished_view = f_student.result()

            assert finished_view.finished_at is not None
            assert adj_view.status in {"PENDING", "APPLIED"}
            with SessionLocal() as db:
                stored_adj = db.get(SessionAdjustment, adj_view.id)
                # Nunca debe quedar PENDING si blocking_session ya terminó
                assert stored_adj.status == "APPLIED"
                assert stored_adj.applied_at is not None
                sr_sets = db.query(student_routine_service.StudentRoutine).filter_by(relationship_id=rel_id).one().days[0]["blocks"][0]["exercises"][0]["sets"]
                assert sr_sets == 4 + iteration

        # Carrera 2: entrenador guarda ajuste mientras alumno inicia nueva sesión sobre una sesión abandonada
        for iteration in range(5):
            with SessionLocal() as db:
                st_u = db.get(User, st_user_id)
                # Sesión anterior abandonada
                start_student_workout_session(db, st_u, WorkoutSessionStartInput(day_name="Día 1"))

            barrier = threading.Barrier(2)

            def _trainer_save_start(iteration=iteration, barrier=barrier):
                with SessionLocal() as tdb:
                    tu = tdb.get(User, tr_user_id)
                    barrier.wait(timeout=5)
                    return session_adjustment_service.save_adjustment(
                        tdb, tu, fin_id,
                        AdjustmentInput.model_validate({
                            "blocks": blocks(ex_id, sets=10 + iteration, reps="6", weight=20 + iteration, rest=60),
                            "note": f"Start race {iteration}",
                        }),
                    )

            def _student_start(barrier=barrier):
                with SessionLocal() as sdb:
                    su = sdb.get(User, st_user_id)
                    barrier.wait(timeout=5)
                    return start_student_workout_session(sdb, su, WorkoutSessionStartInput(day_name="Día 1"))

            with ThreadPoolExecutor(max_workers=2) as pool:
                f_trainer = pool.submit(_trainer_save_start)
                f_student = pool.submit(_student_start)
                adj_view = f_trainer.result()
                new_sess = f_student.result()

            # Debe cumplirse cualquiera de los dos ordenamientos válidos y serializados:
            # (A) save_adjustment fue antes -> APPLIED al iniciar new_sess y snapshot refleja 10+iteration
            # (B) start_session fue antes -> new_sess pasa a ser blocking_session (PENDING sobre new_sess)
            with SessionLocal() as db:
                stored_adj = db.get(SessionAdjustment, adj_view.id)
                from backend.src.models.workout_log import WorkoutSessionSnapshot
                snap = db.get(WorkoutSessionSnapshot, new_sess.id)
                if stored_adj.status == "APPLIED":
                    assert snap.planned_blocks[0]["exercises"][0]["sets"] == 10 + iteration
                else:
                    assert stored_adj.status == "PENDING"
                    assert stored_adj.blocking_session_id == new_sess.id
                    # Limpiar finalizando new_sess para siguiente iteración
                    st_u = db.get(User, st_user_id)
                    finish_student_workout_session(db, st_u, new_sess.id, rpe=7)
                    assert db.get(SessionAdjustment, adj_view.id).status == "APPLIED"
    finally:
        eng.dispose()
