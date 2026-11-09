from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession

TEMPLATES_PATH = "/api/v1/routine-templates"
ASSIGNED_PATH = "/api/v1/students/me/routine-templates/assigned"


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    registration = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "role": role},
    )
    assert registration.status_code == 201
    response = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def link_student(sessions, trainer_email: str, student_email: str) -> str:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))
        profile = StudentProfile(user_id=student_user.id, status="PUBLISHED", created_at=now, updated_at=now)
        plan = TrainingPlan(
            trainer_id=trainer_user.trainer_profile.id,
            title="Plan de musculación",
            monthly_price=Decimal("25000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add_all([profile, plan])
        db.flush()
        relationship = TrainingRelationship(
            student_id=profile.id,
            trainer_id=trainer_user.trainer_profile.id,
            plan_id=plan.id,
            agreed_monthly_price=Decimal("25000.00"),
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=now.date(),
        )
        db.add(relationship)
        db.flush()
        relationship_id = relationship.id
        db.commit()
        return relationship_id


def setup_routine_and_assignment(api, sessions, trainer_headers, student_email: str, trainer_email: str = "trainer_rpe@example.com") -> tuple[str, str, str]:
    ex_res = api.post(
        "/api/v1/exercises",
        headers=trainer_headers,
        json={
            "name": "Press militar",
            "description": "Empuje vertical de hombros",
            "category": "FUERZA",
            "target_muscle_group": "Hombros",
            "equipment_needed": "Mancuernas",
        },
    )
    assert ex_res.status_code == 201
    exercise_id = ex_res.json()["id"]

    routine_res = api.post(
        TEMPLATES_PATH,
        headers=trainer_headers,
        json={
            "name": "Rutina de Hombros",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": "Día 1",
                    "blocks": [
                        {
                            "name": "Fuerza",
                            "exercises": [
                                {
                                    "exercise_id": exercise_id,
                                    "sets": 3,
                                    "reps": "10",
                                    "rest_seconds": 60,
                                    "target_weight_kg": 15,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert routine_res.status_code == 201
    routine_id = routine_res.json()["id"]
    rel_id = link_student(sessions, trainer_email, student_email)
    assigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer_headers,
        json={"routine_template_id": routine_id},
    )
    assert assigned.status_code == 200
    return exercise_id, rel_id, routine_id


def test_finish_session_with_valid_min_rpe_1(client):
    """1. Finalización de sesión con RPE válido mínimo: 1."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe1@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe1@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe1@example.com", "trainer_rpe1@example.com")

    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    finish_res = api.post(
        f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish",
        headers=student,
        json={"rpe": 1},
    )
    assert finish_res.status_code == 200
    data = finish_res.json()
    assert data["finished_at"] is not None
    assert data["rpe"] == 1


def test_finish_session_with_valid_max_rpe_10(client):
    """2. Finalización de sesión con RPE válido máximo: 10."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe2@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe2@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe2@example.com", "trainer_rpe2@example.com")

    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    finish_res = api.post(
        f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish",
        headers=student,
        json={"rpe": 10},
    )
    assert finish_res.status_code == 200
    data = finish_res.json()
    assert data["finished_at"] is not None
    assert data["rpe"] == 10


def test_reject_rpe_equal_to_zero(client):
    """3. Rechazo de RPE igual a 0."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe3@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe3@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe3@example.com", "trainer_rpe3@example.com")

    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    finish_res = api.post(
        f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish",
        headers=student,
        json={"rpe": 0},
    )
    assert finish_res.status_code == 422


def test_reject_rpe_greater_than_10(client):
    """4. Rechazo de RPE superior a 10."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe4@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe4@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe4@example.com", "trainer_rpe4@example.com")

    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    finish_res = api.post(
        f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish",
        headers=student,
        json={"rpe": 11},
    )
    assert finish_res.status_code == 422


def test_reject_decimal_rpe_values(client):
    """5. Rechazo de valores decimales (ej. 7.5)."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe5@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe5@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe5@example.com", "trainer_rpe5@example.com")

    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    finish_res = api.post(
        f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish",
        headers=student,
        json={"rpe": 7.5},
    )
    assert finish_res.status_code == 422


def test_finish_session_without_rpe(client):
    """6 y 7. Finalización sin RPE y persistencia de rpe = NULL."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe6@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe6@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe6@example.com", "trainer_rpe6@example.com")

    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    # Finalizar con payload vacío / rpe = None
    finish_res = api.post(
        f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish",
        headers=student,
        json={},
    )
    assert finish_res.status_code == 200
    data = finish_res.json()
    assert data["finished_at"] is not None
    assert data["rpe"] is None

    # Verificar directamente en la base de datos que se persistió como NULL
    with sessions() as db:
        db_session = db.get(WorkoutSession, session["id"])
        assert db_session is not None
        assert db_session.finished_at is not None
        assert db_session.rpe is None


def test_list_finished_sessions_distinguishes_reported_and_unreported(client):
    """8. Recuperación de sesiones finalizadas con y sin reporte."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe8@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe8@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe8@example.com", "trainer_rpe8@example.com")

    # Sesión 1: finalizada con RPE 8
    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={"rpe": 8})

    # Sesión 2: finalizada sin RPE
    s2 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s2['id']}/finish", headers=student, json={})

    # Consulta de sesiones del alumno
    all_sessions = api.get(f"{ASSIGNED_PATH}/workout-sessions", headers=student).json()
    session_map = {item["id"]: item for item in all_sessions}

    assert session_map[s1["id"]]["rpe"] == 8
    assert session_map[s2["id"]]["rpe"] is None


def test_report_rpe_later_on_previous_session(client):
    """9. Registro posterior de RPE en una sesión anterior."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe9@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe9@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe9@example.com", "trainer_rpe9@example.com")

    # Sesión finalizada sin RPE
    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={})

    # Completar reporte posterior vía PATCH /assigned/workout-sessions/{session_id}/rpe
    patch_res = api.patch(
        f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/rpe",
        headers=student,
        json={"rpe": 6},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["rpe"] == 6

    # Verificar que persiste en DB
    with sessions() as db:
        db_s1 = db.get(WorkoutSession, s1["id"])
        assert db_s1.rpe == 6


def test_rpe_assigned_to_correct_session_and_not_the_new_one(client):
    """10. Verificación de que el RPE se asigna a la sesión correcta y no a la nueva."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe10@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe10@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe10@example.com", "trainer_rpe10@example.com")

    # Sesión anterior finalizada sin RPE
    s_old = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s_old['id']}/finish", headers=student, json={})

    # Alumno inicia una nueva sesión
    s_new = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()

    # El alumno responde al recordatorio y reporta RPE para s_old
    patch_res = api.patch(
        f"{ASSIGNED_PATH}/workout-sessions/{s_old['id']}/rpe",
        headers=student,
        json={"rpe": 7},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["id"] == s_old["id"]
    assert patch_res.json()["rpe"] == 7

    # Verificar que s_new no recibió accidentalmente el RPE y sigue activa/sin finalizar
    with sessions() as db:
        db_old = db.get(WorkoutSession, s_old["id"])
        db_new = db.get(WorkoutSession, s_new["id"])
        assert db_old.rpe == 7
        assert db_new.rpe is None
        assert db_new.finished_at is None


def test_reminder_cleared_after_reporting_rpe(client):
    """11. Desaparición del recordatorio después de completar el reporte."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe11@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe11@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe11@example.com", "trainer_rpe11@example.com")

    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={})

    # Consulta de sesiones: s1 figura pendiente de reporte (rpe is None)
    pending_before = [s for s in api.get(f"{ASSIGNED_PATH}/workout-sessions", headers=student).json() if s["rpe"] is None]
    assert len(pending_before) == 1
    assert pending_before[0]["id"] == s1["id"]

    # Completar reporte
    api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/rpe", headers=student, json={"rpe": 9})

    # Consulta de sesiones: ya no hay sesiones pendientes de reporte
    pending_after = [s for s in api.get(f"{ASSIGNED_PATH}/workout-sessions", headers=student).json() if s["rpe"] is None]
    assert len(pending_after) == 0


def test_idempotent_retry_and_duplicate_report_protection(client):
    """12. Protección ante reintentos o reportes duplicados."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe12@example.com", "TRAINER")
    student = register_and_login(api, "student_rpe12@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_rpe12@example.com", "trainer_rpe12@example.com")

    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={"rpe": 5})

    # Reintento idéntico (misma calificación) -> Debe retornar 200 de forma idempotente
    retry_res = api.patch(
        f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/rpe",
        headers=student,
        json={"rpe": 5},
    )
    assert retry_res.status_code == 200
    assert retry_res.json()["rpe"] == 5

    # Intento de sobrescritura con calificación diferente -> Debe rechazar con 409 Conflict
    conflict_res = api.patch(
        f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/rpe",
        headers=student,
        json={"rpe": 8},
    )
    assert conflict_res.status_code == 409


def test_cannot_report_rpe_on_unfinished_session(client):
    """Validación: No se puede calificar una sesión que aún no finalizó."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_unfin@example.com", "TRAINER")
    student = register_and_login(api, "student_unfin@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_unfin@example.com", "trainer_unfin@example.com")

    s = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    res = api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s['id']}/rpe", headers=student, json={"rpe": 7})
    assert res.status_code == 422


def test_authorization_student_cannot_report_rpe_on_others_session(client):
    """13. Restricciones de autorización: un alumno no puede reportar RPE en la sesión de otro alumno."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_auth@example.com", "TRAINER")
    student1 = register_and_login(api, "student1_auth@example.com", "STUDENT")
    student2 = register_and_login(api, "student2_auth@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student1_auth@example.com", "trainer_auth@example.com")

    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student1, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student1, json={})

    # student2 intenta calificar la sesión de student1
    res = api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/rpe", headers=student2, json={"rpe": 8})
    assert res.status_code == 404


def test_trainer_can_view_student_sessions_with_rpe(client):
    """14. Consulta del RPE desde el seguimiento del entrenador."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_view@example.com", "TRAINER")
    student = register_and_login(api, "student_view@example.com", "STUDENT")
    other_trainer = register_and_login(api, "other_trainer_view@example.com", "TRAINER")
    _, rel_id, _ = setup_routine_and_assignment(api, sessions, trainer, "student_view@example.com", "trainer_view@example.com")

    # Sesión 1 con RPE 9
    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={"rpe": 9})

    # Sesión 2 sin RPE
    s2 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s2['id']}/finish", headers=student, json={})

    # El entrenador consulta las sesiones del alumno
    trainer_sessions_res = api.get(f"{TEMPLATES_PATH}/assignments/{rel_id}/workout-sessions", headers=trainer)
    assert trainer_sessions_res.status_code == 200
    items = trainer_sessions_res.json()
    assert len(items) == 2
    map_items = {it["id"]: it for it in items}
    assert map_items[s1["id"]]["rpe"] == 9
    assert map_items[s2["id"]]["rpe"] is None

    # Otro entrenador intenta consultar esa relación -> Debe retornar 404
    forbidden_res = api.get(f"{TEMPLATES_PATH}/assignments/{rel_id}/workout-sessions", headers=other_trainer)
    assert forbidden_res.status_code == 404


def test_compatibility_with_existing_historical_sessions(client):
    """15. Compatibilidad con sesiones históricas existentes (rpe = NULL)."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_hist@example.com", "TRAINER")
    student = register_and_login(api, "student_hist@example.com", "STUDENT")
    _, rel_id, _ = setup_routine_and_assignment(api, sessions, trainer, "student_hist@example.com", "trainer_hist@example.com")

    # Crear una sesión directamente en la base simulando datos históricos previos a US-60
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        student_user = db.scalar(select(User).where(User.email == "student_hist@example.com"))
        historical_session = WorkoutSession(
            student_id=student_user.student_profile.id,
            relationship_id=rel_id,
            routine_id="historical-routine-123",
            day_name="Día 1",
            modality="GYM",
            started_at=now,
            finished_at=now,
            rpe=None,  # Sesión histórica sin columna RPE poblada
        )
        db.add(historical_session)
        db.commit()
        hist_id = historical_session.id

    # El alumno consulta sus sesiones históricas
    student_sessions = api.get(f"{ASSIGNED_PATH}/workout-sessions", headers=student).json()
    assert any(s["id"] == hist_id and s["rpe"] is None for s in student_sessions)

    # El alumno puede calificar esa sesión histórica posteriormente
    post_report = api.patch(f"{ASSIGNED_PATH}/workout-sessions/{hist_id}/rpe", headers=student, json={"rpe": 8})
    assert post_report.status_code == 200
    assert post_report.json()["rpe"] == 8


def test_concurrency_race_divergent_reports_and_finish_simulation(client):
    """16 (MED-01): Simulación de concurrencia y validación de protección ante reportes divergentes.

    Verifica que una vez persistido un RPE en la sesión (coordinado vía with_for_update en PostgreSQL),
    cualquier reporte divergente concurrente o posterior es estrictamente rechazado con 409 Conflict.
    """
    api, sessions = client
    trainer = register_and_login(api, "trainer_conc@example.com", "TRAINER")
    student = register_and_login(api, "student_conc@example.com", "STUDENT")
    _, _, _ = setup_routine_and_assignment(api, sessions, trainer, "student_conc@example.com", "trainer_conc@example.com")

    # Sesión 1: finalizada sin RPE inicial
    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={})

    # Simulación de carrera: Petición A reporta RPE=6
    res_a = api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/rpe", headers=student, json={"rpe": 6})
    assert res_a.status_code == 200
    assert res_a.json()["rpe"] == 6

    # Petición B intenta concurrentemente/posteriormente registrar RPE=9
    res_b = api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/rpe", headers=student, json={"rpe": 9})
    assert res_b.status_code == 409
    assert "ya cuenta con un reporte de esfuerzo" in res_b.json()["detail"]

    # Sesión 2: finalizada directamente con RPE=7
    s2 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    finish_res = api.post(f"{ASSIGNED_PATH}/workout-sessions/{s2['id']}/finish", headers=student, json={"rpe": 7})
    assert finish_res.status_code == 200
    assert finish_res.json()["rpe"] == 7

    # Intento concurrente/posterior de finalizarla o reportar con RPE divergente (ej. RPE=4) -> 409 Conflict
    conflict_finish = api.post(f"{ASSIGNED_PATH}/workout-sessions/{s2['id']}/finish", headers=student, json={"rpe": 4})
    assert conflict_finish.status_code == 409

    conflict_patch = api.patch(f"{ASSIGNED_PATH}/workout-sessions/{s2['id']}/rpe", headers=student, json={"rpe": 4})
    assert conflict_patch.status_code == 409


def test_database_check_constraint_rejects_out_of_range_rpe(client):
    """17 (BAJ-01): La restricción CHECK a nivel de base de datos rechaza valores de RPE fuera de 1..10."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_chk@example.com", "TRAINER")
    _ = register_and_login(api, "student_chk@example.com", "STUDENT")
    _, rel_id, _ = setup_routine_and_assignment(api, sessions, trainer, "student_chk@example.com", "trainer_chk@example.com")

    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        st_user = db.scalar(select(User).where(User.email == "student_chk@example.com"))
        student_id = st_user.student_profile.id

        # Valores permitidos: None (sin calificar)
        s_null = WorkoutSession(
            student_id=student_id,
            relationship_id=rel_id,
            routine_id="test-routine-chk",
            day_name="Día 1",
            modality="GYM",
            started_at=now,
            finished_at=now,
            rpe=None,
        )
        db.add(s_null)
        db.commit()

        # Valores permitidos: 1 a 10
        s_ok = WorkoutSession(
            student_id=student_id,
            relationship_id=rel_id,
            routine_id="test-routine-chk",
            day_name="Día 1",
            modality="GYM",
            started_at=now,
            finished_at=now,
            rpe=10,
        )
        db.add(s_ok)
        db.commit()

        # Rechazo por CHECK constraint: rpe = 0
        s_zero = WorkoutSession(
            student_id=student_id,
            relationship_id=rel_id,
            routine_id="test-routine-chk",
            day_name="Día 1",
            modality="GYM",
            started_at=now,
            finished_at=now,
            rpe=0,
        )
        db.add(s_zero)
        with pytest.raises(IntegrityError) as exc_zero:
            db.commit()
        assert "ck_workout_sessions_rpe_range" in str(exc_zero.value)
        db.rollback()

        # Rechazo por CHECK constraint: rpe = 11
        s_invalid_high = WorkoutSession(
            student_id=student_id,
            relationship_id=rel_id,
            routine_id="test-routine-chk",
            day_name="Día 1",
            modality="GYM",
            started_at=now,
            finished_at=now,
            rpe=11,
        )
        db.add(s_invalid_high)
        with pytest.raises(IntegrityError) as exc_high:
            db.commit()
        assert "ck_workout_sessions_rpe_range" in str(exc_high.value)
        db.rollback()
