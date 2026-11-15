"""Tests completos de US-29: Alertas de seguridad (CA-1 a CA-5) y aislamiento."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.src.models.safety_alert import SafetyAlert
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.services import (
    abandonment_risk_service,
    body_map_report_service,
    routine_template_service,
    safety_alert_service,
)
from backend.tests.test_us60_rpe_api import setup_routine_and_assignment
from backend.tests.test_us61_body_map_pain_report_api import (
    REPORTS_PATH,
    register_and_login,
    setup_test_environment,
)

ASSIGNED_PATH = "/api/v1/students/me/routine-templates/assigned"
TRAINER_ALERTS_PATH = "/api/v1/trainers/me/safety-alerts"
TRAINER_STUDENTS_PATH = "/api/v1/trainers/me/students"
TRAINER_NOTIFICATIONS_PATH = "/api/v1/trainers/me/notifications"
STUDENT_NOTICES_PATH = "/api/v1/students/me/safety-alerts/reviewed-notices"


def _link_existing_trainer_and_student(
    api,
    sessions,
    *,
    trainer_headers: dict[str, str],
    trainer_email: str,
    student_email: str,
    first_name: str,
    last_name: str,
    with_routine: bool = True,
) -> dict[str, str]:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))

        trainer = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == trainer_user.id))
        if trainer is None:
            trainer = TrainerProfile(
                user_id=trainer_user.id,
                full_name="Entrenador Principal",
                status="PUBLISHED",
                created_at=now,
                updated_at=now,
            )
            db.add(trainer)
            db.flush()

        student = db.scalar(select(StudentProfile).where(StudentProfile.user_id == student_user.id))
        if student is None:
            student = StudentProfile(
                user_id=student_user.id,
                first_name=first_name,
                last_name=last_name,
                status="PUBLISHED",
                created_at=now,
                updated_at=now,
            )
            db.add(student)
            db.flush()

        plan = db.scalar(select(TrainingPlan).where(TrainingPlan.trainer_id == trainer.id))
        if plan is None:
            plan = TrainingPlan(
                trainer_id=trainer.id,
                title="Plan General",
                monthly_price=Decimal("25000.00"),
                currency="ARS",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(plan)
            db.flush()

        relationship = TrainingRelationship(
            student_id=student.id,
            trainer_id=trainer.id,
            plan_id=plan.id,
            agreed_monthly_price=Decimal("25000.00"),
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=now.date(),
        )
        db.add(relationship)
        db.commit()
        rel_id = relationship.id
        student_id = student.id

    exercise_id = None
    if with_routine:
        ex_res = api.post(
            "/api/v1/exercises",
            headers=trainer_headers,
            json={
                "name": f"Sentadilla {first_name}",
                "description": "Ejercicio base",
                "category": "FUERZA",
                "target_muscle_group": "Cuádriceps",
                "equipment_needed": "Barra",
                "has_no_materials_alternative": True,
                "video_platform": "NONE",
            },
        )
        assert ex_res.status_code == 201
        exercise_id = ex_res.json()["id"]
        routine_res = api.post(
            "/api/v1/routine-templates",
            headers=trainer_headers,
            json={
                "name": f"Rutina {first_name}",
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
                                        "reps": "10",
                                        "rest_seconds": 60,
                                        "target_weight_kg": 40,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        )
        assert routine_res.status_code == 201
        assign_res = api.put(
            f"/api/v1/routine-templates/assignments/{rel_id}",
            headers=trainer_headers,
            json={"routine_template_id": routine_res.json()["id"]},
        )
        assert assign_res.status_code == 200

    return {
        "relationship_id": rel_id,
        "student_id": student_id,
        "exercise_id": exercise_id or "",
    }


def _start_session(api, student_headers: dict[str, str], day_name: str = "Día 1") -> str:
    res = api.post(
        f"{ASSIGNED_PATH}/workout-sessions",
        headers=student_headers,
        json={"day_name": day_name},
    )
    assert res.status_code in (200, 201)
    return res.json()["id"]


def _log_set(api, student_headers: dict[str, str], session_id: str, exercise_id: str, exercise_name: str = "Sentadilla") -> None:
    res = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student_headers,
        json={
            "day_name": "Día 1",
            "session_id": session_id,
            "exercise_id": exercise_id,
            "exercise_name": exercise_name,
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 40,
        },
    )
    assert res.status_code == 201


def _report_body_map(
    api,
    student_headers: dict[str, str],
    *,
    zones: list[dict[str, str]],
    context: str = "IN_EXERCISE",
    session_id: str | None = None,
    exercise_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    payload: dict = {"context": context, "zones": zones}
    if session_id is not None:
        payload["session_id"] = session_id
    if exercise_id is not None:
        payload["exercise_id"] = exercise_id
    if idempotency_key is not None:
        payload["idempotency_key"] = idempotency_key
    res = api.post(REPORTS_PATH, headers=student_headers, json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def test_ca1_pain_alerts_single_multi_zone_and_preserves_pain_alert_notification(client):
    """CA-1: crea SafetyAlert(PAIN) por zona con dolor en IN_EXERCISE y POST_SESSION conservando PAIN_ALERT."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca1@example.com", "TRAINER")
    student = register_and_login(api, "student_ca1@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_ca1@example.com", "trainer_ca1@example.com")

    report_in = _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=data["session_id"],
        exercise_id=data["exercise_id"],
        zones=[
            {"zone": "Shoulder", "intensity": "PAIN"},
            {"zone": "Knee", "intensity": "PAIN"},
            {"zone": "Hip", "intensity": "NORMAL"},
        ],
        idempotency_key="ca1-multizone-1",
    )
    _report_body_map(
        api,
        student,
        context="POST_SESSION",
        session_id=data["session_id"],
        zones=[{"zone": "Lower back", "intensity": "PAIN"}],
        idempotency_key="ca1-post-session-1",
    )

    alerts_res = api.get(TRAINER_ALERTS_PATH, headers=trainer)
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) == 3
    assert all(item["alert_type"] == "PAIN" and item["status"] == "PENDING" for item in alerts)
    zones = {item["zone"]: item for item in alerts}
    assert set(zones.keys()) == {"Shoulder", "Knee", "Lower back"}
    assert zones["Shoulder"]["exercise_id"] == data["exercise_id"]
    assert zones["Shoulder"]["session_id"] == data["session_id"]
    assert zones["Lower back"]["exercise_id"] is None
    assert zones["Lower back"]["session_id"] == data["session_id"]

    # Preserva la notificación PAIN_ALERT existente de US-61 apuntando al reporte original
    notif_res = api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer)
    assert notif_res.status_code == 200
    pain_notifs = [n for n in notif_res.json()["items"] if n["type"] == "PAIN_ALERT"]
    assert len(pain_notifs) == 2
    assert any(
        n["related_entity_type"] == "BODY_MAP_PAIN_REPORT" and n["related_entity_id"] == report_in["id"]
        for n in pain_notifs
    )


def test_ca2_repeated_discomfort_two_consecutive_sessions_and_normal_ignored(client, monkeypatch):
    """CA-2: DISCOMFORT en misma zona en 2 sesiones consecutivas genera alerta y NORMAL no la dispara."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca2_basic@example.com", "TRAINER")
    student = register_and_login(api, "student_ca2_basic@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca2_basic@example.com",
        student_email="student_ca2_basic@example.com",
        first_name="Lucia",
        last_name="Gomez",
    )
    t0 = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t0.replace(tzinfo=None))
    s1 = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=s1,
        exercise_id=ctx["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}, {"zone": "Elbow", "intensity": "NORMAL"}],
    )
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1}/finish", headers=student, json={}).status_code == 200
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json() == []

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=2)).replace(tzinfo=None))
    s2 = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="POST_SESSION",
        session_id=s2,
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}, {"zone": "Elbow", "intensity": "NORMAL"}],
    )

    alerts = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "REPEATED_DISCOMFORT"
    assert alerts[0]["zone"] == "Knee"
    assert alerts[0]["zone_display_name"] == "Rodilla"
    assert alerts[0]["session_id"] == s2
    assert alerts[0]["status"] == "PENDING"

    notif_items = api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer).json()["items"]
    rep_notifs = [n for n in notif_items if n["type"] == "REPEATED_DISCOMFORT_ALERT"]
    assert len(rep_notifs) == 1
    assert rep_notifs[0]["related_entity_type"] == "SAFETY_ALERT"
    assert rep_notifs[0]["related_entity_id"] == alerts[0]["id"]


def test_ca2_interrupted_by_finished_intermediate_session_with_activity(client, monkeypatch):
    """CA-2: sesión intermedia finalizada con actividad sin molestia en la zona interrumpe la consecutividad."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca2_fin@example.com", "TRAINER")
    student = register_and_login(api, "student_ca2_fin@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca2_fin@example.com",
        student_email="student_ca2_fin@example.com",
        first_name="Martin",
        last_name="Paz",
    )
    t0 = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)

    # S1: DISCOMFORT Knee
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t0.replace(tzinfo=None))
    s1 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s1, exercise_id=ctx["exercise_id"], zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1}/finish", headers=student, json={})

    # S2: intermedia iniciada, finalizada y con WorkoutSetLog (y solo molestia en hombro / carga normal en rodilla)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=2)).replace(tzinfo=None))
    s2 = _start_session(api, student)
    _log_set(api, student, s2, ctx["exercise_id"])
    _report_body_map(api, student, context="POST_SESSION", session_id=s2, zones=[{"zone": "Shoulder", "intensity": "DISCOMFORT"}, {"zone": "Knee", "intensity": "NORMAL"}])
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s2}/finish", headers=student, json={})

    # S3: vuelve a tener DISCOMFORT Knee -> NO debe disparar alerta porque S2 cortó la serie
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=4)).replace(tzinfo=None))
    s3 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s3, exercise_id=ctx["exercise_id"], zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json() == []

    # S4: segunda consecutiva tras S3 -> ahora SÍ dispara
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=6)).replace(tzinfo=None))
    s4 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s4, exercise_id=ctx["exercise_id"], zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    alerts = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert len(alerts) == 1
    assert alerts[0]["session_id"] == s4


def test_ca2_interrupted_by_unfinished_intermediate_session_with_activity(client, monkeypatch):
    """CA-2: sesión intermedia iniciada, SIN FINALIZAR y con actividad registrada también interrumpe."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca2_unfin@example.com", "TRAINER")
    student = register_and_login(api, "student_ca2_unfin@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca2_unfin@example.com",
        student_email="student_ca2_unfin@example.com",
        first_name="Sofia",
        last_name="Diaz",
    )
    t0 = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t0.replace(tzinfo=None))
    s1 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s1, exercise_id=ctx["exercise_id"], zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1}/finish", headers=student, json={})

    # S2: iniciada con una serie registrada pero NO finalizada (finished_at IS NULL)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=2)).replace(tzinfo=None))
    s2 = _start_session(api, student)
    _log_set(api, student, s2, ctx["exercise_id"])
    with sessions() as db:
        db_s2 = db.get(WorkoutSession, s2)
        assert db_s2 is not None and db_s2.finished_at is None

    # S3: DISCOMFORT Knee -> NO dispara porque S2 fue iniciada, tuvo actividad y no tuvo DISCOMFORT en Knee
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=4)).replace(tzinfo=None))
    s3 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s3, exercise_id=ctx["exercise_id"], zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json() == []


def test_ca2_unstarted_day_empty_session_and_unlinked_post_session_do_not_interrupt(client, monkeypatch):
    """CA-2: días no iniciados, sesiones sin actividad registrada y POST_SESSION sin session_id no cortan ni disparan."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca2_noirq@example.com", "TRAINER")
    student = register_and_login(api, "student_ca2_noirq@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca2_noirq@example.com",
        student_email="student_ca2_noirq@example.com",
        first_name="Pablo",
        last_name="Vega",
    )
    t0 = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)

    # S1: DISCOMFORT Shoulder
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t0.replace(tzinfo=None))
    s1 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s1, exercise_id=ctx["exercise_id"], zones=[{"zone": "Shoulder", "intensity": "DISCOMFORT"}])
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1}/finish", headers=student, json={})

    # Reporte POST_SESSION histórico/huérfano sin session_id: ni dispara ni interrumpe
    _report_body_map(api, student, context="POST_SESSION", session_id=None, zones=[{"zone": "Shoulder", "intensity": "DISCOMFORT"}])
    _report_body_map(api, student, context="POST_SESSION", session_id=None, zones=[{"zone": "Shoulder", "intensity": "NORMAL"}])
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json() == []

    # Día de rutina asignada nunca iniciado (no se llama a POST workout-sessions)
    # + Sesión iniciada y finalizada SIN actividad registrada (sin sets ni body map reports)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=2)).replace(tzinfo=None))
    s_empty_finished = _start_session(api, student)
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_empty_finished}/finish", headers=student, json={})

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=3)).replace(tzinfo=None))
    _start_session(api, student)  # Sesión iniciada sin finalizar ni actividad

    # S4: DISCOMFORT Shoulder -> S1 sigue siendo la sesión participante inmediatamente anterior => SÍ alerta
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=4)).replace(tzinfo=None))
    s4 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s4, exercise_id=ctx["exercise_id"], zones=[{"zone": "Shoulder", "intensity": "DISCOMFORT"}])

    alerts = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "REPEATED_DISCOMFORT"
    assert alerts[0]["zone"] == "Shoulder"
    assert alerts[0]["session_id"] == s4


def test_ca2_multiple_discomfort_reports_in_same_session_count_as_one_session(client, monkeypatch):
    """CA-2: dos o más reportes DISCOMFORT en misma zona y misma sesión cuentan como una única sesión."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca2_same@example.com", "TRAINER")
    student = register_and_login(api, "student_ca2_same@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca2_same@example.com",
        student_email="student_ca2_same@example.com",
        first_name="Clara",
        last_name="Rios",
    )
    t0 = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)

    # Dentro de S1 hay 2 reportes DISCOMFORT Knee (IN_EXERCISE + POST_SESSION): NO debe auto-disparar
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t0.replace(tzinfo=None))
    s1 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s1, exercise_id=ctx["exercise_id"], zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    _report_body_map(api, student, context="POST_SESSION", session_id=s1, zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json() == []

    # Dentro de S2 vuelve a reportar 2 veces DISCOMFORT Knee -> debe crear exactamente 1 sola alerta y 1 notificación
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=2)).replace(tzinfo=None))
    s2 = _start_session(api, student)
    _report_body_map(api, student, context="IN_EXERCISE", session_id=s2, exercise_id=ctx["exercise_id"], zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])
    _report_body_map(api, student, context="POST_SESSION", session_id=s2, zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}])

    alerts = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert len(alerts) == 1
    assert alerts[0]["session_id"] == s2
    rep_notifs = [n for n in api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer).json()["items"] if n["type"] == "REPEATED_DISCOMFORT_ALERT"]
    assert len(rep_notifs) == 1


def test_ca3_excessive_effort_finish_deferred_below_threshold_and_concurrency(client, monkeypatch):
    """CA-3: RPE 9/10 al finalizar y diferido crean 1 alerta y notificación; <=8 no; idempotente bajo concurrencia."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca3@example.com", "TRAINER")
    student = register_and_login(api, "student_ca3@example.com", "STUDENT")
    setup_routine_and_assignment(api, sessions, trainer, "student_ca3@example.com", "trainer_ca3@example.com")

    # 1) RPE <= 8 no genera alerta
    s_ok = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()["id"]
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_ok}/finish", headers=student, json={"rpe": 8}).status_code == 200
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json() == []

    # 2) Finalizar con RPE 9 genera alerta y notificación
    s_9 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()["id"]
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_9}/finish", headers=student, json={"rpe": 9}).status_code == 200

    # Reenvío de finish con mismo rpe=9 es idempotente sin duplicar alerta ni notificación
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_9}/finish", headers=student, json={"rpe": 9}).status_code == 200

    # 3) Finalizar sin RPE y reportar RPE 10 diferido genera alerta
    s_10 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()["id"]
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_10}/finish", headers=student, json={}).status_code == 200
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert len(api.get(TRAINER_ALERTS_PATH, headers=trainer).json()) == 1
    assert api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s_10}/rpe", headers=student, json={"rpe": 10}).status_code == 200
    # Reenvío diferido idempotente
    assert api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s_10}/rpe", headers=student, json={"rpe": 10}).status_code == 200

    alerts = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert len(alerts) == 2
    assert {a["rpe"] for a in alerts} == {9, 10}
    assert all(a["alert_type"] == "EXCESSIVE_EFFORT" for a in alerts)
    notifs = [n for n in api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer).json()["items"] if n["type"] == "EXCESSIVE_EFFORT_ALERT"]
    assert len(notifs) == 2

    # 4) Simulación de IntegrityError concurrente en _create_alert_idempotent recupera alerta existente sin fallar
    with sessions() as db:
        ws = db.get(WorkoutSession, s_10)
        assert ws is not None
        original_flush = db.flush

        def raise_once(*args, **kwargs):
            raise IntegrityError("race", params=(), orig=Exception("UNIQUE constraint failed"))

        # Eliminar pre-check temporalmente para forzar el path except IntegrityError
        monkeypatch.setattr(safety_alert_service, "select", select)
        db.flush = raise_once  # type: ignore[method-assign]
        existing = db.scalar(select(SafetyAlert).where(SafetyAlert.dedup_key == f"EXCESSIVE_EFFORT:{s_10}"))
        assert existing is not None
        db.flush = original_flush  # type: ignore[method-assign]

        # Test directo de _create_alert_idempotent con colisión simulada en flush
        calls = {"count": 0}
        orig_scalar = db.scalar

        def scalar_miss_first(stmt, *args, **kwargs):
            if calls["count"] == 0 and "dedup_key" in str(stmt):
                calls["count"] += 1
                return None
            return orig_scalar(stmt, *args, **kwargs)

        monkeypatch.setattr(db, "scalar", scalar_miss_first)
        alert_obj, created = safety_alert_service._create_alert_idempotent(
            db,
            relationship_id=existing.relationship_id,
            trainer_id=existing.trainer_id,
            student_id=existing.student_id,
            session_id=s_10,
            report_id=None,
            exercise_id=None,
            alert_type="EXCESSIVE_EFFORT",
            zone=None,
            rpe=10,
            dedup_key=f"EXCESSIVE_EFFORT:{s_10}",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        assert created is False
        assert alert_obj.id == existing.id


def test_ca4_prioritization_above_abandonment_risk_notifications_and_review_actions(client, monkeypatch):
    """CA-4: US-29 prioriza por encima de US-32; lectura de notificación no revisa la alerta; 3 acciones y nota."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca4@example.com", "TRAINER")
    st_normal = register_and_login(api, "st_normal@example.com", "STUDENT")
    register_and_login(api, "st_risk@example.com", "STUDENT")
    st_alert = register_and_login(api, "st_alert@example.com", "STUDENT")

    _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca4@example.com",
        student_email="st_normal@example.com",
        first_name="Alba", last_name="Alpha",
    )
    _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca4@example.com",
        student_email="st_risk@example.com",
        first_name="Beto", last_name="Risk",
    )
    alert_ctx = _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca4@example.com",
        student_email="st_alert@example.com",
        first_name="Zoe", last_name="Zeta",
    )

    today = datetime.now(UTC)
    # Hacemos pasar 15 días para que st_risk esté en riesgo (sin entrenamientos) mientras st_normal y st_alert acaban de entrenar
    later = today + timedelta(days=15)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: later.replace(tzinfo=None))
    monkeypatch.setattr(abandonment_risk_service, "utc_now", lambda: later.replace(tzinfo=None))

    s_norm = _start_session(api, st_normal)
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_norm}/finish", headers=st_normal, json={"rpe": 7}).status_code == 200

    # st_alert genera 3 alertas (1 PAIN, 1 EXCESSIVE_EFFORT, 1 REPEATED_DISCOMFORT) para probar las 3 acciones
    s_a1 = _start_session(api, st_alert)
    _report_body_map(
        api,
        st_alert,
        context="IN_EXERCISE",
        session_id=s_a1,
        exercise_id=alert_ctx["exercise_id"],
        zones=[{"zone": "Wrist and hand", "intensity": "DISCOMFORT"}, {"zone": "Neck", "intensity": "PAIN"}],
    )
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_a1}/finish", headers=st_alert, json={"rpe": 9}).status_code == 200

    later2 = later + timedelta(hours=4)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: later2.replace(tzinfo=None))
    monkeypatch.setattr(abandonment_risk_service, "utc_now", lambda: later2.replace(tzinfo=None))
    s_a2 = _start_session(api, st_alert)
    _report_body_map(
        api,
        st_alert,
        context="IN_EXERCISE",
        session_id=s_a2,
        exercise_id=alert_ctx["exercise_id"],
        zones=[{"zone": "Wrist and hand", "intensity": "DISCOMFORT"}],
    )

    # Marcar notificaciones como leídas NO marca las SafetyAlert como REVIEWED
    notifs = api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer).json()["items"]
    assert len(notifs) >= 2
    for notif in notifs:
        read_res = api.patch(f"/api/v1/trainers/me/notifications/{notif['id']}/read", headers=trainer)
        assert read_res.status_code == 200
        assert read_res.json()["is_read"] is True

    # Verifica orden 3 niveles: (1) Zoe Zeta (US-29 pending=3) > (2) Beto Risk (US-32) > (3) Alba Alpha
    listed = api.get(TRAINER_STUDENTS_PATH, headers=trainer).json()
    assert [item["full_name"] for item in listed] == ["Zoe Zeta", "Beto Risk", "Alba Alpha"]
    assert listed[0]["unreviewed_alert_count"] == 3
    assert listed[1]["unreviewed_alert_count"] == 0

    # Verifica safety_indicators en el detalle del alumno
    detail = api.get(f"{TRAINER_STUDENTS_PATH}/{alert_ctx['student_id']}", headers=trainer).json()
    assert len(detail["limitations"]["safety_indicators"]) == 3

    # Revisar las 3 alertas con las 3 acciones distintas (+ nota en 2, sin nota en 1) y validar 409 en segunda revisión
    student_alerts = api.get(f"/api/v1/trainers/me/students/{alert_ctx['student_id']}/safety-alerts", headers=trainer).json()
    by_type = {item["alert_type"]: item for item in student_alerts}
    assert set(by_type.keys()) == {"PAIN", "REPEATED_DISCOMFORT", "EXCESSIVE_EFFORT"}

    # Validar 422 RFC 7807 con acción inválida o nota > 500
    bad_action = api.patch(
        f"{TRAINER_ALERTS_PATH}/{by_type['PAIN']['id']}/review",
        headers=trainer,
        json={"action_taken": "INVALID_ACTION"},
    )
    assert bad_action.status_code == 422
    assert "application/problem+json" in bad_action.headers["content-type"]

    long_note = api.patch(
        f"{TRAINER_ALERTS_PATH}/{by_type['PAIN']['id']}/review",
        headers=trainer,
        json={"action_taken": "ADJUSTED_ROUTINE", "trainer_note": "x" * 501},
    )
    assert long_note.status_code == 422
    assert "application/problem+json" in long_note.headers["content-type"]

    r1 = api.patch(
        f"{TRAINER_ALERTS_PATH}/{by_type['PAIN']['id']}/review",
        headers=trainer,
        json={"action_taken": "ADJUSTED_ROUTINE", "trainer_note": "Cambiamos carga esta semana"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "REVIEWED"
    assert r1.json()["action_taken"] == "ADJUSTED_ROUTINE"
    assert r1.json()["trainer_note"] == "Cambiamos carga esta semana"

    # Revisar nuevamente -> 409 Conflict
    dup_review = api.patch(
        f"{TRAINER_ALERTS_PATH}/{by_type['PAIN']['id']}/review",
        headers=trainer,
        json={"action_taken": "NO_ACTION"},
    )
    assert dup_review.status_code == 409
    assert "application/problem+json" in dup_review.headers["content-type"]

    r2 = api.patch(
        f"{TRAINER_ALERTS_PATH}/{by_type['REPEATED_DISCOMFORT']['id']}/review",
        headers=trainer,
        json={"action_taken": "CONTACTED_STUDENT", "trainer_note": "   "},
    )
    assert r2.status_code == 200
    assert r2.json()["trainer_note"] is None

    r3 = api.patch(
        f"{TRAINER_ALERTS_PATH}/{by_type['EXCESSIVE_EFFORT']['id']}/review",
        headers=trainer,
        json={"action_taken": "NO_ACTION", "trainer_note": "Controlado"},
    )
    assert r3.status_code == 200

    # Al revisar todas las pendientes de Zoe, vuelve a prioridad de US-32 (Beto Risk ahora primero, luego orden alfabético por apellido)
    listed_after = api.get(TRAINER_STUDENTS_PATH, headers=trainer).json()
    assert [item["full_name"] for item in listed_after] == ["Beto Risk", "Alba Alpha", "Zoe Zeta"]
    assert all(item["unreviewed_alert_count"] == 0 for item in listed_after)


def test_ca5_student_reviewed_notices_pain_only_with_or_without_note_and_single_consumption(client, monkeypatch):
    """CA-5: aviso exclusivo para PAIN con/sin nota, excluye molestia repetida y RPE, consumo único."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca5@example.com", "TRAINER")
    student = register_and_login(api, "student_ca5@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca5@example.com",
        student_email="student_ca5@example.com",
        first_name="Valen",
        last_name="Lopez",
    )
    t0 = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t0.replace(tzinfo=None))
    s1 = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=s1,
        exercise_id=ctx["exercise_id"],
        zones=[{"zone": "Elbow", "intensity": "DISCOMFORT"}, {"zone": "Lower back", "intensity": "PAIN"}],
    )
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1}/finish", headers=student, json={"rpe": 10})

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: (t0 + timedelta(days=1)).replace(tzinfo=None))
    s2 = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=s2,
        exercise_id=ctx["exercise_id"],
        zones=[{"zone": "Elbow", "intensity": "DISCOMFORT"}, {"zone": "Shoulder", "intensity": "PAIN"}],
    )

    alerts = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    pain_alerts = sorted([a for a in alerts if a["alert_type"] == "PAIN"], key=lambda a: a["zone"])
    other_alerts = [a for a in alerts if a["alert_type"] != "PAIN"]
    assert len(pain_alerts) == 2
    assert len(other_alerts) == 2  # REPEATED_DISCOMFORT + EXCESSIVE_EFFORT

    # Entrenador revisa TODAS las alertas (una PAIN con nota, una PAIN sin nota, REPEATED_DISCOMFORT y EXCESSIVE_EFFORT con nota)
    api.patch(
        f"{TRAINER_ALERTS_PATH}/{pain_alerts[0]['id']}/review",
        headers=trainer,
        json={"action_taken": "ADJUSTED_ROUTINE", "trainer_note": "Bajamos intensidad"},
    )
    api.patch(
        f"{TRAINER_ALERTS_PATH}/{pain_alerts[1]['id']}/review",
        headers=trainer,
        json={"action_taken": "CONTACTED_STUDENT"},
    )
    for other in other_alerts:
        res_other = api.patch(
            f"{TRAINER_ALERTS_PATH}/{other['id']}/review",
            headers=trainer,
            json={"action_taken": "ADJUSTED_ROUTINE", "trainer_note": "Nota interna"},
        )
        assert res_other.status_code == 200

    # Alumno consulta avisos para su próxima sesión: EXCLUSIVAMENTE los 2 de PAIN
    notices = api.get(STUDENT_NOTICES_PATH, headers=student).json()
    assert len(notices) == 2
    by_id = {n["id"]: n for n in notices}
    assert set(by_id.keys()) == {pain_alerts[0]["id"], pain_alerts[1]["id"]}
    assert by_id[pain_alerts[0]["id"]]["action_taken"] == "ADJUSTED_ROUTINE"
    assert by_id[pain_alerts[0]["id"]]["trainer_note"] == "Bajamos intensidad"
    assert by_id[pain_alerts[1]["id"]]["action_taken"] == "CONTACTED_STUDENT"
    assert by_id[pain_alerts[1]["id"]]["trainer_note"] is None

    # No se puede marcar seen sobre molestia repetida ni esfuerzo excesivo
    for other in other_alerts:
        seen_other = api.post(f"/api/v1/students/me/safety-alerts/{other['id']}/seen", headers=student)
        assert seen_other.status_code == 404

    # Marcar como vistos los avisos PAIN los consume una sola vez
    for notice in notices:
        seen_res = api.post(f"/api/v1/students/me/safety-alerts/{notice['id']}/seen", headers=student)
        assert seen_res.status_code == 200
        # Reenvío idempotente
        assert api.post(f"/api/v1/students/me/safety-alerts/{notice['id']}/seen", headers=student).status_code == 200

    assert api.get(STUDENT_NOTICES_PATH, headers=student).json() == []


def test_security_alerts_isolation_roles_and_relationship_termination(client):
    """Aislamiento estricto por rol y vínculo ACTIVE (otros entrenadores, alumnos, terminación y cambio de entrenador)."""
    api, sessions = client
    trainer_a = register_and_login(api, "trainer_iso_a@example.com", "TRAINER")
    trainer_b = register_and_login(api, "trainer_iso_b@example.com", "TRAINER")
    student_1 = register_and_login(api, "student_iso_1@example.com", "STUDENT")
    student_2 = register_and_login(api, "student_iso_2@example.com", "STUDENT")

    ctx_1a = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer_a,
        trainer_email="trainer_iso_a@example.com",
        student_email="student_iso_1@example.com",
        first_name="Alumno",
        last_name="Uno",
    )
    _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer_b,
        trainer_email="trainer_iso_b@example.com",
        student_email="student_iso_2@example.com",
        first_name="Alumno",
        last_name="Dos",
    )

    s1 = _start_session(api, student_1)
    _report_body_map(
        api,
        student_1,
        context="IN_EXERCISE",
        session_id=s1,
        exercise_id=ctx_1a["exercise_id"],
        zones=[{"zone": "Hip", "intensity": "PAIN"}],
    )

    alerts_a = api.get(TRAINER_ALERTS_PATH, headers=trainer_a).json()
    assert len(alerts_a) == 1
    alert_id = alerts_a[0]["id"]

    # Roles cruzados -> 403 RFC 7807
    r_forbidden_t = api.get(TRAINER_ALERTS_PATH, headers=student_1)
    assert r_forbidden_t.status_code == 403
    assert "application/problem+json" in r_forbidden_t.headers["content-type"]
    r_forbidden_s = api.get(STUDENT_NOTICES_PATH, headers=trainer_a)
    assert r_forbidden_s.status_code == 403
    assert "application/problem+json" in r_forbidden_s.headers["content-type"]

    # Entrenador B no puede listar ni revisar la alerta de Entrenador A
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer_b).json() == []
    assert api.get(f"/api/v1/trainers/me/students/{ctx_1a['student_id']}/safety-alerts", headers=trainer_b).status_code == 404
    assert api.patch(
        f"{TRAINER_ALERTS_PATH}/{alert_id}/review",
        headers=trainer_b,
        json={"action_taken": "NO_ACTION"},
    ).status_code == 404

    # Alumno 2 no puede marcar vista la alerta de Alumno 1
    api.patch(
        f"{TRAINER_ALERTS_PATH}/{alert_id}/review",
        headers=trainer_a,
        json={"action_taken": "CONTACTED_STUDENT"},
    )
    assert api.post(f"/api/v1/students/me/safety-alerts/{alert_id}/seen", headers=student_2).status_code == 404

    # Generamos otra alerta PENDING para alumno 1 y terminamos su vínculo con entrenador A
    _report_body_map(
        api,
        student_1,
        context="POST_SESSION",
        session_id=s1,
        zones=[{"zone": "Ankle and foot", "intensity": "PAIN"}],
    )
    pending_before_term = api.get(TRAINER_ALERTS_PATH, headers=trainer_a, params={"status": "PENDING"}).json()
    assert len(pending_before_term) == 1

    with sessions() as db:
        rel_a = db.get(TrainingRelationship, ctx_1a["relationship_id"])
        assert rel_a is not None
        rel_a.status = "TERMINATED"
        db.commit()

    # Al terminar el vínculo: desaparecen alertas, prioridad y avisos pendientes
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer_a).json() == []
    assert api.get(f"/api/v1/trainers/me/students/{ctx_1a['student_id']}/safety-alerts", headers=trainer_a).status_code == 404
    assert api.patch(
        f"{TRAINER_ALERTS_PATH}/{pending_before_term[0]['id']}/review",
        headers=trainer_a,
        json={"action_taken": "NO_ACTION"},
    ).status_code == 404
    assert api.get(STUDENT_NOTICES_PATH, headers=student_1).json() == []
    assert api.post(f"/api/v1/students/me/safety-alerts/{alert_id}/seen", headers=student_1).status_code == 404

    # Al vincular Alumno 1 con Entrenador B, inicia limpio sin heredar alertas del vínculo anterior
    _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer_b,
        trainer_email="trainer_iso_b@example.com",
        student_email="student_iso_1@example.com",
        first_name="Alumno",
        last_name="Uno",
        with_routine=False,
    )
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer_b).json() == []
    assert api.get(STUDENT_NOTICES_PATH, headers=student_1).json() == []


def test_ca2_interrupted_by_intermediate_session_with_pain_only(client, monkeypatch):
    """CA-2: S1 DISCOMFORT Knee -> S2 PAIN Knee -> S3 DISCOMFORT Knee no dispara REPEATED_DISCOMFORT."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_ca2_pain_irq@example.com", "TRAINER")
    student = register_and_login(api, "student_ca2_pain_irq@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer,
        trainer_email="trainer_ca2_pain_irq@example.com",
        student_email="student_ca2_pain_irq@example.com",
        first_name="Nora",
        last_name="Salas",
    )
    t0 = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)

    # S1: DISCOMFORT Knee
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t0.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t0.replace(tzinfo=None))
    s1 = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=s1,
        exercise_id=ctx["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer).json() == []

    # S2: PAIN Knee (sin DISCOMFORT en Knee) -> crea alerta PAIN + PAIN_ALERT e interrumpe la secuencia CA-2
    t1 = t0 + timedelta(days=2)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t1.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t1.replace(tzinfo=None))
    s2 = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=s2,
        exercise_id=ctx["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "PAIN"}],
    )

    alerts_after_s2 = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert len(alerts_after_s2) == 1
    assert alerts_after_s2[0]["alert_type"] == "PAIN"
    assert alerts_after_s2[0]["session_id"] == s2
    notifs_after_s2 = api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer).json()["items"]
    assert len([n for n in notifs_after_s2 if n["type"] == "PAIN_ALERT"]) == 1

    # S3: DISCOMFORT Knee -> NO debe disparar REPEATED_DISCOMFORT por S1-S2-S3
    t2 = t0 + timedelta(days=4)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t2.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t2.replace(tzinfo=None))
    s3 = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=s3,
        exercise_id=ctx["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )

    alerts_after_s3 = api.get(TRAINER_ALERTS_PATH, headers=trainer).json()
    assert [a["alert_type"] for a in alerts_after_s3] == ["PAIN"]
    notifs_after_s3 = api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer).json()["items"]
    assert len([n for n in notifs_after_s3 if n["type"] == "PAIN_ALERT"]) == 1
    assert [n for n in notifs_after_s3 if n["type"] == "REPEATED_DISCOMFORT_ALERT"] == []


def test_ca2_late_reports_abc_chronological_and_out_of_order(client, monkeypatch):
    """CA-2 (LOW-04): A, B, C en orden cronológico normal y cuando A se reporta tardíamente sin duplicados."""
    api, sessions = client

    # Escenario 1: A, B y C con DISCOMFORT en rodilla registrados en orden cronológico normal
    trainer_1 = register_and_login(api, "trainer_abc_norm@example.com", "TRAINER")
    student_1 = register_and_login(api, "student_abc_norm@example.com", "STUDENT")
    ctx_1 = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer_1,
        trainer_email="trainer_abc_norm@example.com",
        student_email="student_abc_norm@example.com",
        first_name="Lucas",
        last_name="Vera",
    )
    t_a = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    t_b = datetime(2026, 8, 1, 11, 0, tzinfo=UTC)
    t_c = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    norm_sessions = []
    for moment in (t_a, t_b, t_c):
        monkeypatch.setattr(routine_template_service, "utc_now", lambda m=moment: m.replace(tzinfo=None))
        monkeypatch.setattr(body_map_report_service, "utc_now", lambda m=moment: m.replace(tzinfo=None))
        sid = _start_session(api, student_1)
        _report_body_map(
            api,
            student_1,
            context="IN_EXERCISE",
            session_id=sid,
            exercise_id=ctx_1["exercise_id"],
            zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
        )
        norm_sessions.append(sid)

    norm_alerts = api.get(TRAINER_ALERTS_PATH, headers=trainer_1).json()
    assert {a["session_id"] for a in norm_alerts} == {norm_sessions[1], norm_sessions[2]}
    assert all(a["alert_type"] == "REPEATED_DISCOMFORT" for a in norm_alerts)

    # Escenario 2: A (10:00), B (11:00), C (12:00) pero A se reporta tardíamente a las 13:00 (y se repite a las 13:05)
    trainer_2 = register_and_login(api, "trainer_abc_late@example.com", "TRAINER")
    student_2 = register_and_login(api, "student_abc_late@example.com", "STUDENT")
    ctx_2 = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer_2,
        trainer_email="trainer_abc_late@example.com",
        student_email="student_abc_late@example.com",
        first_name="Mia",
        last_name="Sosa",
    )

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t_a.replace(tzinfo=None))
    sess_a = _start_session(api, student_2)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t_b.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t_b.replace(tzinfo=None))
    sess_b = _start_session(api, student_2)
    _report_body_map(
        api,
        student_2,
        context="IN_EXERCISE",
        session_id=sess_b,
        exercise_id=ctx_2["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t_c.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t_c.replace(tzinfo=None))
    sess_c = _start_session(api, student_2)
    _report_body_map(
        api,
        student_2,
        context="IN_EXERCISE",
        session_id=sess_c,
        exercise_id=ctx_2["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )

    # Hasta acá solo existe la alerta de (B -> C) sobre sess_c
    before_late = api.get(TRAINER_ALERTS_PATH, headers=trainer_2).json()
    assert [a["session_id"] for a in before_late] == [sess_c]

    # A se reporta tardíamente a las 13:00 con DISCOMFORT en rodilla -> debe detectar el par consecutivo (A -> B)
    t_late_1 = datetime(2026, 8, 1, 13, 0, tzinfo=UTC)
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t_late_1.replace(tzinfo=None))
    _report_body_map(
        api,
        student_2,
        context="IN_EXERCISE",
        session_id=sess_a,
        exercise_id=ctx_2["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )

    after_late = api.get(TRAINER_ALERTS_PATH, headers=trainer_2).json()
    assert len(after_late) == 2
    assert {a["session_id"] for a in after_late} == {sess_b, sess_c}
    rep_notifs = [
        n
        for n in api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer_2).json()["items"]
        if n["type"] == "REPEATED_DISCOMFORT_ALERT"
    ]
    assert len(rep_notifs) == 2

    # Reporte tardío repetido sobre A (POST_SESSION, fuera de ventana de 10s) no debe duplicar alertas ni notificaciones
    t_late_2 = datetime(2026, 8, 1, 13, 5, tzinfo=UTC)
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t_late_2.replace(tzinfo=None))
    _report_body_map(
        api,
        student_2,
        context="POST_SESSION",
        session_id=sess_a,
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )
    after_repeat = api.get(TRAINER_ALERTS_PATH, headers=trainer_2).json()
    assert len(after_repeat) == 2
    rep_notifs_repeat = [
        n
        for n in api.get(TRAINER_NOTIFICATIONS_PATH, headers=trainer_2).json()["items"]
        if n["type"] == "REPEATED_DISCOMFORT_ALERT"
    ]
    assert len(rep_notifs_repeat) == 2


def test_ca2_late_report_interruption_different_zone_and_relationship_isolation(client, monkeypatch):
    """CA-2 (LOW-04): B sin molestia interrumpe (A, B, C), otra zona no dispara y vínculos terminados/ajenos quedan aislados."""
    api, sessions = client
    trainer_1 = register_and_login(api, "trainer_late_iso1@example.com", "TRAINER")
    trainer_2 = register_and_login(api, "trainer_late_iso2@example.com", "TRAINER")
    student = register_and_login(api, "student_late_iso@example.com", "STUDENT")
    ctx = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer_1,
        trainer_email="trainer_late_iso1@example.com",
        student_email="student_late_iso@example.com",
        first_name="Ivo",
        last_name="Ramos",
    )

    t_a = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)
    t_b = datetime(2026, 8, 2, 11, 0, tzinfo=UTC)
    t_c = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

    # A (10:00) iniciada sin reporte todavía
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t_a.replace(tzinfo=None))
    sess_a = _start_session(api, student)

    # B (11:00) participante con serie registrada (sin DISCOMFORT en rodilla)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t_b.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t_b.replace(tzinfo=None))
    sess_b = _start_session(api, student)
    _log_set(api, student, sess_b, ctx["exercise_id"])
    _report_body_map(
        api,
        student,
        context="POST_SESSION",
        session_id=sess_b,
        zones=[{"zone": "Knee", "intensity": "NORMAL"}],
    )

    # C (12:00) con DISCOMFORT en rodilla
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: t_c.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: t_c.replace(tzinfo=None))
    sess_c = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=sess_c,
        exercise_id=ctx["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )

    # A se reporta tardíamente con DISCOMFORT Knee (B corta la secuencia) y también con DISCOMFORT Shoulder (zona distinta)
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: datetime(2026, 8, 2, 13, 0, tzinfo=UTC).replace(tzinfo=None))
    _report_body_map(
        api,
        student,
        context="POST_SESSION",
        session_id=sess_a,
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}, {"zone": "Shoulder", "intensity": "DISCOMFORT"}],
    )
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer_1).json() == []

    # Caso de vínculo terminado + otro entrenador: sesión vieja S0 (09:00) del vínculo 1 terminado no dispara tras cambio de vínculo
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: datetime(2026, 8, 2, 9, 0, tzinfo=UTC).replace(tzinfo=None))
    sess_0 = _start_session(api, student)
    # Terminar vínculo con trainer_1 antes del reporte tardío sobre sess_0
    with sessions() as db:
        rel_1 = db.get(TrainingRelationship, ctx["relationship_id"])
        assert rel_1 is not None
        rel_1.status = "TERMINATED"
        db.commit()

    ctx_2 = _link_existing_trainer_and_student(
        api,
        sessions,
        trainer_headers=trainer_2,
        trainer_email="trainer_late_iso2@example.com",
        student_email="student_late_iso@example.com",
        first_name="Ivo",
        last_name="Ramos",
    )
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer_2).json() == []
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: datetime(2026, 8, 2, 14, 0, tzinfo=UTC).replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: datetime(2026, 8, 2, 14, 0, tzinfo=UTC).replace(tzinfo=None))
    sess_new = _start_session(api, student)
    _report_body_map(
        api,
        student,
        context="IN_EXERCISE",
        session_id=sess_new,
        exercise_id=ctx_2["exercise_id"],
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )

    # Reporte tardío sobre sess_0 perteneciente al vínculo terminado con trainer_1
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: datetime(2026, 8, 2, 15, 0, tzinfo=UTC).replace(tzinfo=None))
    _report_body_map(
        api,
        student,
        context="POST_SESSION",
        session_id=sess_0,
        zones=[{"zone": "Knee", "intensity": "DISCOMFORT"}],
    )

    assert api.get(TRAINER_ALERTS_PATH, headers=trainer_1).json() == []
    assert api.get(TRAINER_ALERTS_PATH, headers=trainer_2).json() == []


def test_low01_consistent_alphabetical_full_name_ordering_and_filters(client, monkeypatch):
    """LOW-01 + filtros API: orden alfabético por apellido y nombre consistente en desempates y tercer nivel."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_low01@example.com", "TRAINER")
    st_zoe_alpha = register_and_login(api, "st_zoe_alpha@example.com", "STUDENT")
    st_ana_alpha = register_and_login(api, "st_ana_alpha@example.com", "STUDENT")
    st_alba_zeta = register_and_login(api, "st_alba_zeta@example.com", "STUDENT")
    register_and_login(api, "st_bruno_risk@example.com", "STUDENT")
    register_and_login(api, "st_dario_risk@example.com", "STUDENT")

    ctx_zoe = _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_low01@example.com",
        student_email="st_zoe_alpha@example.com",
        first_name="Zoe", last_name="Alpha",
    )
    ctx_ana = _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_low01@example.com",
        student_email="st_ana_alpha@example.com",
        first_name="Ana", last_name="Alpha",
    )
    ctx_alba = _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_low01@example.com",
        student_email="st_alba_zeta@example.com",
        first_name="Alba", last_name="Zeta",
    )
    _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_low01@example.com",
        student_email="st_bruno_risk@example.com",
        first_name="Bruno", last_name="Zeta",
    )
    _link_existing_trainer_and_student(
        api, sessions,
        trainer_headers=trainer,
        trainer_email="trainer_low01@example.com",
        student_email="st_dario_risk@example.com",
        first_name="Dario", last_name="Alpha",
    )

    later = datetime.now(UTC) + timedelta(days=16)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: later.replace(tzinfo=None))
    monkeypatch.setattr(body_map_report_service, "utc_now", lambda: later.replace(tzinfo=None))
    monkeypatch.setattr(abandonment_risk_service, "utc_now", lambda: later.replace(tzinfo=None))

    # Zoe Alpha, Ana Alpha y Alba Zeta entrenan hoy (sin riesgo, Tier 2 Resto)
    s_zoe = _start_session(api, st_zoe_alpha)
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_zoe}/finish", headers=st_zoe_alpha, json={"rpe": 6}).status_code == 200
    s_ana = _start_session(api, st_ana_alpha)
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_ana}/finish", headers=st_ana_alpha, json={"rpe": 6}).status_code == 200
    s_alba = _start_session(api, st_alba_zeta)
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_alba}/finish", headers=st_alba_zeta, json={"rpe": 6}).status_code == 200

    # Tier 1 (US-32 empate en days_without_report): Dario Alpha antes que Bruno Zeta (apellido Alpha < Zeta)
    # Tier 2 (Resto sin alertas ni riesgo): Ana Alpha, Zoe Alpha, Alba Zeta (por apellido, desempatando por nombre)
    listed = api.get(TRAINER_STUDENTS_PATH, headers=trainer).json()
    assert [item["full_name"] for item in listed] == [
        "Dario Alpha",
        "Bruno Zeta",
        "Ana Alpha",
        "Zoe Alpha",
        "Alba Zeta",
    ]

    # También en Tier 0 (US-29 empate en count y timestamp) y verifica filtros ?student_id y ?status=PENDING
    _report_body_map(
        api, st_alba_zeta, context="IN_EXERCISE", session_id=s_alba,
        exercise_id=ctx_alba["exercise_id"], zones=[{"zone": "Shoulder", "intensity": "PAIN"}],
    )
    _report_body_map(
        api, st_zoe_alpha, context="IN_EXERCISE", session_id=s_zoe,
        exercise_id=ctx_zoe["exercise_id"], zones=[{"zone": "Knee", "intensity": "PAIN"}],
    )
    _report_body_map(
        api, st_ana_alpha, context="IN_EXERCISE", session_id=s_ana,
        exercise_id=ctx_ana["exercise_id"], zones=[{"zone": "Hip", "intensity": "PAIN"}],
    )

    listed_with_alerts = api.get(TRAINER_STUDENTS_PATH, headers=trainer).json()
    assert [item["full_name"] for item in listed_with_alerts] == [
        "Ana Alpha",
        "Zoe Alpha",
        "Alba Zeta",
        "Dario Alpha",
        "Bruno Zeta",
    ]

    filtered_alba = api.get(TRAINER_ALERTS_PATH, headers=trainer, params={"student_id": ctx_alba["student_id"], "status": "PENDING"}).json()
    assert len(filtered_alba) == 1
    assert filtered_alba[0]["student_id"] == ctx_alba["student_id"]

    # CA-5 seen sobre alerta PAIN todavía PENDING debe devolver 404
    pending_pain_id = filtered_alba[0]["id"]
    assert api.post(f"/api/v1/students/me/safety-alerts/{pending_pain_id}/seen", headers=st_alba_zeta).status_code == 404

    alba_pending = api.get(
        f"/api/v1/trainers/me/students/{ctx_alba['student_id']}/safety-alerts",
        headers=trainer,
        params={"status": "PENDING"},
    ).json()
    assert len(alba_pending) == 1
    assert alba_pending[0]["id"] == pending_pain_id
