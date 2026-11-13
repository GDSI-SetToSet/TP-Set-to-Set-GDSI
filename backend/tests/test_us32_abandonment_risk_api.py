from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.src.models.student_profile import StudentProfile
from backend.src.models.student_routine import StudentRoutine
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.services import abandonment_risk_service, routine_template_service
from backend.src.services.abandonment_risk_service import (
    REASON_INACTIVE_TWO_WEEKS,
    REASON_MISSED_TRAININGS,
    evaluate_risk,
)
from backend.tests.test_workout_session_api import (
    ASSIGNED_PATH,
    TEMPLATES_PATH,
    create_assigned_routine,
    link_student,
    register_and_login,
)

RISK_PATH = "/api/v1/trainers/me/abandonment-risk"
NOTIFICATIONS_PATH = "/api/v1/trainers/me/notifications"


def test_evaluate_risk_uses_whichever_threshold_comes_first():
    # 3 entrenamientos por semana: 5 sin reportar a los 12 días, antes de las 2 semanas.
    assert evaluate_risk(11, 3) == (False, None, 4)
    assert evaluate_risk(12, 3) == (True, REASON_MISSED_TRAININGS, 5)
    # 1 entrenamiento por semana: las 2 semanas llegan antes que 5 entrenamientos.
    assert evaluate_risk(13, 1) == (False, None, 1)
    assert evaluate_risk(14, 1) == (True, REASON_INACTIVE_TWO_WEEKS, 2)
    # Sin rutina no se esperan entrenamientos.
    assert evaluate_risk(60, 0) == (False, None, 0)


def at(monkeypatch, moment: datetime) -> None:
    monkeypatch.setattr(abandonment_risk_service, "utc_now", lambda: moment.replace(tzinfo=None))


def risk_by_student(api, trainer) -> dict[str, dict]:
    response = api.get(RISK_PATH, headers=trainer)
    assert response.status_code == 200
    return {item["student_name"]: item for item in response.json()}


def abandonment_notifications(api, trainer) -> list[dict]:
    items = api.get(NOTIFICATIONS_PATH, headers=trainer, params={"limit": 100}).json()["items"]
    return [item for item in items if item["type"] == "ABANDONMENT_RISK"]


def test_alerts_once_per_inactivity_period_and_sorts_risky_students_first(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    active = register_and_login(api, "active@example.com", "STUDENT")
    register_and_login(api, "idle@example.com", "STUDENT")
    register_and_login(api, "no-routine@example.com", "STUDENT")
    create_assigned_routine(api, sessions, trainer, "active@example.com")
    create_assigned_routine(api, sessions, trainer, "idle@example.com")
    link_student(sessions, "trainer@example.com", "no-routine@example.com")
    today = datetime.now(UTC)

    at(monkeypatch, today + timedelta(days=3))
    early = api.get(RISK_PATH, headers=trainer).json()
    assert len(early) == 3
    assert not any(item["at_risk"] for item in early)
    assert abandonment_notifications(api, trainer) == []

    # Pasadas 2 semanas, el alumno activo reporta un entrenamiento y el otro no.
    later = today + timedelta(days=15)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: later)
    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=active, json={"day_name": "Día 1"}).json()
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish", headers=active).status_code == 200

    at(monkeypatch, later)
    response = api.get(RISK_PATH, headers=trainer).json()
    assert response[0]["at_risk"] is True
    assert [item["at_risk"] for item in response] == [True, False, False]
    risk = {item["relationship_id"]: item for item in response}
    idle = response[0]
    assert idle["reason"] == REASON_INACTIVE_TWO_WEEKS
    assert idle["days_without_report"] == 15
    assert idle["weekly_trainings"] == 1
    assert idle["last_report_at"] is None
    reporting = next(item for item in risk.values() if item["last_report_at"] is not None)
    assert reporting["days_without_report"] == 0
    no_routine = next(item for item in risk.values() if item["weekly_trainings"] == 0)
    assert no_routine["at_risk"] is False

    alerts = abandonment_notifications(api, trainer)
    assert len(alerts) == 1
    assert alerts[0]["related_student_id"] == idle["student_id"]
    assert alerts[0]["related_entity_id"] == idle["relationship_id"]
    assert "no reporta entrenamientos hace 15 días" in alerts[0]["message"]

    # Consultar de nuevo no duplica la alerta del mismo período.
    api.get(RISK_PATH, headers=trainer)
    assert len(abandonment_notifications(api, trainer)) == 1

    # Dos semanas después del último reporte, el alumno que había entrenado también entra en riesgo.
    at(monkeypatch, later + timedelta(days=14))
    assert len(abandonment_notifications(api, trainer)) == 2
    assert [item["at_risk"] for item in api.get(RISK_PATH, headers=trainer).json()] == [True, True, False]


def test_notifications_endpoint_generates_alert_and_risk_is_private(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    register_and_login(api, "idle@example.com", "STUDENT")
    create_assigned_routine(api, sessions, trainer, "idle@example.com")
    other_trainer = register_and_login(api, "other-trainer@example.com", "TRAINER")
    student = register_and_login(api, "student-only@example.com", "STUDENT")

    at(monkeypatch, datetime.now(UTC) + timedelta(days=20))

    assert len(abandonment_notifications(api, trainer)) == 1
    assert api.get(RISK_PATH, headers=other_trainer).json() == []
    assert abandonment_notifications(api, other_trainer) == []
    assert api.get(RISK_PATH, headers=student).status_code in (403, 404)
    assert api.get(RISK_PATH).status_code == 401


def test_notifications_still_load_if_risk_evaluation_fails(client, monkeypatch):
    api, _ = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")

    def boom(*_args, **_kwargs):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr("backend.src.api.v1.discovery.list_abandonment_risk", boom)

    response = api.get(NOTIFICATIONS_PATH, headers=trainer)
    assert response.status_code == 200


def _create_template(api, trainer, name: str, day_count: int) -> str:
    exercise = api.post(
        "/api/v1/exercises",
        headers=trainer,
        json={
            "name": f"Ejercicio {name}",
            "description": "Descripción",
            "category": "FUERZA",
            "target_muscle_group": "Piernas",
            "equipment_needed": "Mancuerna",
        },
    )
    assert exercise.status_code == 201
    ex_id = exercise.json()["id"]
    response = api.post(
        TEMPLATES_PATH,
        headers=trainer,
        json={
            "name": name,
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": f"Día {idx + 1}",
                    "blocks": [
                        {
                            "name": "Principal",
                            "exercises": [
                                {"exercise_id": ex_id, "sets": 3, "reps": "10", "rest_seconds": 60}
                            ],
                        }
                    ],
                }
                for idx in range(day_count)
            ],
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_new_routine_on_old_relationship_without_student_routine_has_no_false_positive(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    register_and_login(api, "old-student@example.com", "STUDENT")
    template_id = _create_template(api, trainer, "Fuerza 3 días", day_count=3)
    rel_id = link_student(sessions, "trainer@example.com", "old-student@example.com")

    today = datetime.now(UTC)
    with sessions() as db:
        rel = db.get(TrainingRelationship, rel_id)
        rel.start_date = (today - timedelta(days=25)).date()
        db.commit()

    monkeypatch.setattr(routine_template_service, "utc_now", lambda: today.replace(tzinfo=None))
    assigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": template_id},
    )
    assert assigned.status_code == 200

    with sessions() as db:
        assert db.scalar(select(StudentRoutine).where(StudentRoutine.relationship_id == rel_id)) is None

    at(monkeypatch, today)
    immediate = api.get(RISK_PATH, headers=trainer).json()
    assert len(immediate) == 1
    assert immediate[0]["weekly_trainings"] == 3
    assert immediate[0]["days_without_report"] == 0
    assert immediate[0]["at_risk"] is False
    assert abandonment_notifications(api, trainer) == []

    # Recién al alcanzarse el umbral de 5 entrenamientos esperados (12 días con 3 días/semana) entra en riesgo.
    at(monkeypatch, today + timedelta(days=12))
    delayed = api.get(RISK_PATH, headers=trainer).json()
    assert delayed[0]["at_risk"] is True
    assert delayed[0]["reason"] == REASON_MISSED_TRAININGS
    assert delayed[0]["missed_trainings"] == 5
    assert len(abandonment_notifications(api, trainer)) == 1


def test_reassigning_routine_resets_period_without_losing_historical_sessions(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    student = register_and_login(api, "reassigned@example.com", "STUDENT")
    _, rel_id = create_assigned_routine(api, sessions, trainer, "reassigned@example.com")

    day0 = datetime.now(UTC) - timedelta(days=25)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: day0)
    # Alumno materializa StudentRoutine y finaliza una sesión histórica hace 23 días.
    assert api.get(ASSIGNED_PATH, headers=student).status_code == 200
    session_time = day0 + timedelta(days=2)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: session_time)
    sess = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{sess['id']}/finish", headers=student).status_code == 200

    with sessions() as db:
        day0_naive = day0.replace(tzinfo=None)
        sr = StudentRoutine(
            relationship_id=rel_id,
            source_kind="GENERIC",
            name="Rutina Inicial",
            duration_weeks=4,
            intensity="MEDIA",
            days=[{"name": "Día 1", "blocks": []}],
            draft_version=1,
            status="ACTIVE",
            created_at=day0_naive,
            updated_at=day0_naive,
        )
        db.add(sr)
        rel = db.get(TrainingRelationship, rel_id)
        rel.start_date = day0.date()
        rel.routine_assigned_at = day0_naive
        db.commit()
        original_created_at = sr.created_at

    # Hoy el entrenador reasigna una nueva rutina de 2 días/semana.
    reassign_time = datetime.now(UTC)
    new_template_id = _create_template(api, trainer, "Rutina Reasignada", day_count=2)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: reassign_time.replace(tzinfo=None))
    reassigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": new_template_id},
    )
    assert reassigned.status_code == 200

    # No se elimina historial ni se altera created_at original de StudentRoutine.
    with sessions() as db:
        sr = db.scalar(select(StudentRoutine).where(StudentRoutine.relationship_id == rel_id))
        assert sr.created_at == original_created_at
        assert db.scalar(select(WorkoutSession).where(WorkoutSession.id == sess["id"])) is not None

    at(monkeypatch, reassign_time)
    after_reassign = api.get(RISK_PATH, headers=trainer).json()
    assert after_reassign[0]["at_risk"] is False
    assert after_reassign[0]["days_without_report"] == 0
    assert after_reassign[0]["last_report_at"] is None
    assert abandonment_notifications(api, trainer) == []

    # Pasadas 2 semanas desde la reasignación sin reportes nuevos, sí detecta riesgo.
    at(monkeypatch, reassign_time + timedelta(days=14))
    expired = api.get(RISK_PATH, headers=trainer).json()
    assert expired[0]["at_risk"] is True
    assert expired[0]["reason"] == REASON_INACTIVE_TWO_WEEKS
    assert len(abandonment_notifications(api, trainer)) == 1


def test_students_endpoint_orders_abandonment_risk_first_with_stable_secondary_order(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    other_trainer = register_and_login(api, "other@example.com", "TRAINER")

    for email in ("zoe@example.com", "ana@example.com", "carlos@example.com", "bruno@example.com", "ajeno@example.com"):
        register_and_login(api, email, "STUDENT")

    _, rel_zoe = create_assigned_routine(api, sessions, trainer, "zoe@example.com")
    _, rel_ana = create_assigned_routine(api, sessions, trainer, "ana@example.com")
    _, rel_carlos = create_assigned_routine(api, sessions, trainer, "carlos@example.com")
    _, rel_bruno = create_assigned_routine(api, sessions, trainer, "bruno@example.com")
    _create_template(api, other_trainer, "Rutina Ajena", day_count=1)
    rel_ajeno = link_student(sessions, "other@example.com", "ajeno@example.com")

    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        names = {
            "zoe@example.com": ("Zoe", "Alfa"),
            "ana@example.com": ("Ana", "Beta"),
            "carlos@example.com": ("Carlos", "Gamma"),
            "bruno@example.com": ("Bruno", "Delta"),
        }
        for email, (first, last) in names.items():
            user = db.scalar(select(User).where(User.email == email))
            profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
            profile.first_name = first
            profile.last_name = last

        # Bruno (30 días sin reportar) y Ana (20 días) en riesgo; Zoe y Carlos asignados hoy (sin riesgo).
        db.get(TrainingRelationship, rel_bruno).start_date = (now - timedelta(days=30)).date()
        db.get(TrainingRelationship, rel_bruno).routine_assigned_at = now - timedelta(days=30)
        db.get(TrainingRelationship, rel_ana).start_date = (now - timedelta(days=20)).date()
        db.get(TrainingRelationship, rel_ana).routine_assigned_at = now - timedelta(days=20)
        db.get(TrainingRelationship, rel_zoe).routine_assigned_at = now
        db.get(TrainingRelationship, rel_carlos).routine_assigned_at = now
        # Vínculo de otro entrenador no debe aparecer en el listado de trainer.
        other_rel = db.get(TrainingRelationship, rel_ajeno)
        other_rel.start_date = (now - timedelta(days=40)).date()
        db.commit()

    at(monkeypatch, now)
    response = api.get("/api/v1/trainers/me/students", headers=trainer)

    assert response.status_code == 200
    assert [item["full_name"] for item in response.json()] == [
        "Bruno Delta",
        "Ana Beta",
        "Zoe Alfa",
        "Carlos Gamma",
    ]

    other_response = api.get("/api/v1/trainers/me/students", headers=other_trainer)
    assert other_response.status_code == 200
    assert [item["full_name"] for item in other_response.json()] == ["ajeno@example.com"]


def test_legacy_relationship_with_null_routine_assigned_at_and_no_student_routine_avoids_false_positive(
    client, monkeypatch
):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    register_and_login(api, "legacy-unstarted@example.com", "STUDENT")
    register_and_login(api, "legacy-active-tpl@example.com", "STUDENT")
    template_id = _create_template(api, trainer, "Plantilla Heredada", day_count=2)
    rel_unstarted = link_student(sessions, "trainer@example.com", "legacy-unstarted@example.com")
    rel_started = link_student(sessions, "trainer@example.com", "legacy-active-tpl@example.com")

    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        for rel_id in (rel_unstarted, rel_started):
            rel = db.get(TrainingRelationship, rel_id)
            rel.start_date = (now - timedelta(days=30)).date()
            rel.initial_routine_id = template_id
            rel.routine_assigned_at = None

        # Alumno A tiene sesión histórica de una rutina previa hace 20 días, pero ninguna en la plantilla vigente.
        r1 = db.get(TrainingRelationship, rel_unstarted)
        db.add(
            WorkoutSession(
                student_id=r1.student_id,
                relationship_id=r1.id,
                routine_id="old-template-id",
                day_name="Día 1",
                modality="GYM",
                started_at=now - timedelta(days=20),
                finished_at=now - timedelta(days=20),
            )
        )
        # Alumno B sí empezó esta misma plantilla hace 20 días y dejó de entrenar.
        r2 = db.get(TrainingRelationship, rel_started)
        db.add(
            WorkoutSession(
                student_id=r2.student_id,
                relationship_id=r2.id,
                routine_id=template_id,
                day_name="Día 1",
                modality="GYM",
                started_at=now - timedelta(days=20),
                finished_at=now - timedelta(days=20),
            )
        )
        db.commit()

    at(monkeypatch, now)
    risks = {item["relationship_id"]: item for item in api.get(RISK_PATH, headers=trainer).json()}

    assert risks[rel_unstarted]["at_risk"] is False
    assert risks[rel_unstarted]["days_without_report"] == 0
    assert risks[rel_unstarted]["last_report_at"] is None
    assert risks[rel_started]["at_risk"] is True
    assert risks[rel_started]["days_without_report"] == 20

    # El historial antiguo se conserva intacto y, si siguen 14 días sin actividad en la plantilla vigente, sí alerta.
    with sessions() as db:
        assert db.scalar(select(WorkoutSession).where(WorkoutSession.relationship_id == rel_unstarted)) is not None
        assert db.get(TrainingRelationship, rel_unstarted).routine_assigned_at is not None

    at(monkeypatch, now + timedelta(days=14))
    risks_later = {item["relationship_id"]: item for item in api.get(RISK_PATH, headers=trainer).json()}
    assert risks_later[rel_unstarted]["at_risk"] is True
    assert risks_later[rel_unstarted]["reason"] == REASON_INACTIVE_TWO_WEEKS
