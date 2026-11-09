from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from backend.src.models.notification import Notification
from backend.src.models.personal_record import PersonalRecord
from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSetLog

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


def link_student(
    sessions, trainer_email: str, student_email: str, first_name: str = "Juan", last_name: str = "Perez"
) -> str:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))
        profile = StudentProfile(
            user_id=student_user.id,
            first_name=first_name,
            last_name=last_name,
            status="PUBLISHED",
            created_at=now,
            updated_at=now,
        )
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


def setup_routine_and_exercises(api, sessions, trainer_headers, student_email: str):
    # Exercise 1: Sentadilla
    ex1_res = api.post(
        "/api/v1/exercises",
        headers=trainer_headers,
        json={
            "name": "Sentadilla",
            "description": "Flexión de piernas",
            "category": "FUERZA",
            "target_muscle_group": "Piernas",
            "equipment_needed": "Barra",
        },
    )
    assert ex1_res.status_code == 201
    ex1_id = ex1_res.json()["id"]

    # Exercise 2: Press de banca
    ex2_res = api.post(
        "/api/v1/exercises",
        headers=trainer_headers,
        json={
            "name": "Press de banca",
            "description": "Empuje horizontal de pecho",
            "category": "FUERZA",
            "target_muscle_group": "Pecho",
            "equipment_needed": "Barra y banco",
        },
    )
    assert ex2_res.status_code == 201
    ex2_id = ex2_res.json()["id"]

    routine_res = api.post(
        TEMPLATES_PATH,
        headers=trainer_headers,
        json={
            "name": "Rutina de Fuerza",
            "duration_weeks": 4,
            "intensity": "ALTA",
            "days": [
                {
                    "name": "Día 1",
                    "blocks": [
                        {
                            "name": "Fuerza Principal",
                            "exercises": [
                                {
                                    "exercise_id": ex1_id,
                                    "sets": 3,
                                    "reps": "8",
                                    "rest_seconds": 90,
                                    "target_weight_kg": 50,
                                },
                                {
                                    "exercise_id": ex2_id,
                                    "sets": 3,
                                    "reps": "8",
                                    "rest_seconds": 90,
                                    "target_weight_kg": 40,
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert routine_res.status_code == 201
    routine_id = routine_res.json()["id"]
    rel_id = link_student(sessions, "trainer_pr@example.com", student_email)
    assigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer_headers,
        json={"routine_template_id": routine_id},
    )
    assert assigned.status_code == 200
    return ex1_id, ex2_id, rel_id, routine_id


def test_first_positive_weight_set_sets_initial_personal_record_and_notifies_trainer(client):
    """CA-1, CA-2, CA-3: El primer registro con carga positiva establece el récord inicial y avisa al entrenador."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, _, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    # Iniciar sesión de entrenamiento
    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    assert session_res.status_code == 201
    session_id = session_res.json()["id"]

    # Registrar primera serie con 50 kg
    log_res = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 50.0,
            "session_id": session_id,
        },
    )
    assert log_res.status_code == 201
    body = log_res.json()
    assert body["is_personal_record"] is True
    assert body["is_initial_pr"] is True
    assert body["pr_previous_weight_kg"] is None
    assert body["weight_kg"] == 50.0

    # Verificar en base de datos la entidad PersonalRecord
    with sessions() as db:
        pr = db.scalar(select(PersonalRecord).where(PersonalRecord.exercise_id == ex1_id))
        assert pr is not None
        assert float(pr.weight_kg) == 50.0
        assert pr.reps_completed == "8"
        assert pr.workout_set_log_id == body["id"]

        # Verificar notificación al entrenador
        trainer_user = db.scalar(select(User).where(User.email == "trainer_pr@example.com"))
        notifications = db.scalars(
            select(Notification).where(
                Notification.recipient_id == trainer_user.id,
                Notification.type == "PERSONAL_RECORD",
            )
        ).all()
        assert len(notifications) == 1
        notif = notifications[0]
        assert "Juan Perez" in notif.title
        assert "Sentadilla" in notif.message
        assert "50 kg" in notif.message
        assert "primer récord" in notif.message


def test_subsequent_set_equal_or_lower_weight_does_not_trigger_pr(client):
    """CA-1, CA-2: Cargas iguales o inferiores al récord no constituyen un nuevo PR ni generan alertas duplicadas."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, _, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    # Serie 1: 60 kg (PR inicial)
    res1 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 60.0,
            "session_id": session_id,
        },
    )
    assert res1.status_code == 201
    assert res1.json()["is_personal_record"] is True

    # Serie 2: 60 kg (igual)
    res2 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "8",
            "weight_kg": 60.0,
            "session_id": session_id,
        },
    )
    assert res2.status_code == 201
    assert res2.json()["is_personal_record"] is False
    assert res2.json()["pr_previous_weight_kg"] is None

    # Serie 3: 50 kg (menor)
    res3 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 3,
            "reps_completed": "8",
            "weight_kg": 50.0,
            "session_id": session_id,
        },
    )
    assert res3.status_code == 201
    assert res3.json()["is_personal_record"] is False

    # El entrenador debe mantener exactamente 1 notificación (la inicial)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == "trainer_pr@example.com"))
        notifications = db.scalars(
            select(Notification).where(
                Notification.recipient_id == trainer_user.id,
                Notification.type == "PERSONAL_RECORD",
            )
        ).all()
        assert len(notifications) == 1

        # El PR vigente sigue siendo 60 kg de la serie 1
        pr = db.scalar(select(PersonalRecord).where(PersonalRecord.exercise_id == ex1_id))
        assert float(pr.weight_kg) == 60.0
        assert pr.workout_set_log_id == res1.json()["id"]


def test_subsequent_set_strictly_higher_weight_triggers_new_pr_and_replaces_previous(client):
    """CA-1, CA-2, CA-3: Una carga que supera estrictamente el PR reemplaza el récord vigente y notifica con comparativa."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, _, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    # Serie 1: 50 kg (inicial)
    res1 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 50.0,
            "session_id": session_id,
        },
    )
    assert res1.status_code == 201
    assert res1.json()["is_personal_record"] is True

    # Serie 2: 55.5 kg (nuevo PR)
    res2 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "8",
            "weight_kg": 55.5,
            "session_id": session_id,
        },
    )
    assert res2.status_code == 201
    body2 = res2.json()
    assert body2["is_personal_record"] is True
    assert body2["is_initial_pr"] is False
    assert body2["pr_previous_weight_kg"] == 50.0
    assert body2["weight_kg"] == 55.5

    # Verificar que en la tabla personal_records se reemplazó el anterior
    with sessions() as db:
        records = db.scalars(select(PersonalRecord).where(PersonalRecord.exercise_id == ex1_id)).all()
        assert len(records) == 1
        pr = records[0]
        assert float(pr.weight_kg) == 55.5
        assert pr.workout_set_log_id == body2["id"]
        assert pr.reps_completed == "8"

        # Verificar 2 notificaciones al entrenador
        trainer_user = db.scalar(select(User).where(User.email == "trainer_pr@example.com"))
        notifications = db.scalars(
            select(Notification)
            .where(
                Notification.recipient_id == trainer_user.id,
                Notification.type == "PERSONAL_RECORD",
            )
            .order_by(Notification.created_at.asc())
        ).all()
        assert len(notifications) == 2
        notif2 = notifications[1]
        assert "superó su récord personal" in notif2.message
        assert "55.5 kg" in notif2.message
        assert "50 kg" in notif2.message


def test_bodyweight_zero_weight_does_not_create_pr(client):
    """Una serie de peso corporal (0 kg) no establece récord ni genera notificaciones de PR."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, _, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    res = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "15",
            "weight_kg": 0.0,
            "session_id": session_id,
        },
    )
    assert res.status_code == 201
    assert res.json()["is_personal_record"] is False

    with sessions() as db:
        pr_count = db.scalar(select(PersonalRecord).where(PersonalRecord.exercise_id == ex1_id))
        assert pr_count is None
        notif_count = db.scalar(select(Notification).where(Notification.type == "PERSONAL_RECORD"))
        assert notif_count is None


def test_student_isolation_records_do_not_leak_across_students(client):
    """Aislamiento entre alumnos: los récords de un alumno no interfieren con los de otro."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student1 = register_and_login(api, "student1@example.com", "STUDENT")
    student2 = register_and_login(api, "student2@example.com", "STUDENT")

    ex1_id, _, _, routine_id = setup_routine_and_exercises(api, sessions, trainer, "student1@example.com")
    rel2_id = link_student(sessions, "trainer_pr@example.com", "student2@example.com", "Maria", "Gomez")
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel2_id}",
        headers=trainer,
        json={"routine_template_id": routine_id},
    )

    # Student 1 levanta 100 kg
    s1_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student1, json={"day_name": "Día 1"})
    log1 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student1,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "5",
            "weight_kg": 100.0,
            "session_id": s1_res.json()["id"],
        },
    )
    assert log1.json()["is_personal_record"] is True
    assert log1.json()["is_initial_pr"] is True

    # Student 2 levanta 30 kg en el mismo ejercicio -> debe ser su propio récord inicial
    s2_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student2, json={"day_name": "Día 1"})
    log2 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student2,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 30.0,
            "session_id": s2_res.json()["id"],
        },
    )
    assert log2.json()["is_personal_record"] is True
    assert log2.json()["is_initial_pr"] is True

    # Student 2 luego levanta 35 kg -> nuevo PR para student 2, sin importar los 100 kg de student 1
    log3 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student2,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "8",
            "weight_kg": 35.0,
            "session_id": s2_res.json()["id"],
        },
    )
    assert log3.json()["is_personal_record"] is True
    assert log3.json()["pr_previous_weight_kg"] == 30.0


def test_exercise_isolation_records_do_not_leak_across_exercises(client):
    """Aislamiento entre ejercicios: el PR de un ejercicio no afecta al de otro ejercicio."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, ex2_id, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    # Ex1 (Sentadilla): 80 kg
    log_ex1 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 80.0,
            "session_id": session_id,
        },
    )
    assert log_ex1.json()["is_personal_record"] is True

    # Ex2 (Press de banca): 40 kg -> Es récord inicial de Ex2 aunque 40 < 80
    log_ex2 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex2_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 40.0,
            "session_id": session_id,
        },
    )
    assert log_ex2.json()["is_personal_record"] is True
    assert log_ex2.json()["is_initial_pr"] is True

    with sessions() as db:
        records = db.scalars(select(PersonalRecord)).all()
        assert len(records) == 2


def test_deleting_pr_set_recalculates_to_previous_highest_set(client):
    """Al eliminar la serie que sostenía el PR vigente, se recalcula al anterior récord de la historia."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, _, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    # Serie 1: 50 kg
    log1 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 50.0,
            "session_id": session_id,
        },
    ).json()

    # Serie 2: 70 kg (Nuevo PR)
    log2 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "6",
            "weight_kg": 70.0,
            "session_id": session_id,
        },
    ).json()

    # Desmarcar/eliminar la serie 2
    del_res = api.delete(f"{ASSIGNED_PATH}/workout-logs/{log2['id']}", headers=student)
    assert del_res.status_code == 204

    # El PR debe haber vuelto automáticamente a 50 kg (apuntando a log1)
    with sessions() as db:
        pr = db.scalar(select(PersonalRecord).where(PersonalRecord.exercise_id == ex1_id))
        assert pr is not None
        assert float(pr.weight_kg) == 50.0
        assert pr.workout_set_log_id == log1["id"]

    # Si se desmarca también la serie 1, el registro PR se elimina por completo
    del1_res = api.delete(f"{ASSIGNED_PATH}/workout-logs/{log1['id']}", headers=student)
    assert del1_res.status_code == 204
    with sessions() as db:
        pr = db.scalar(select(PersonalRecord).where(PersonalRecord.exercise_id == ex1_id))
        assert pr is None


def test_deleting_non_pr_set_leaves_pr_untouched(client):
    """Eliminar una serie que no era el PR vigente no altera el registro de récord."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, _, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    # Serie 1: 60 kg (PR)
    log1 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 60.0,
            "session_id": session_id,
        },
    ).json()

    # Serie 2: 40 kg (no es PR)
    log2 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "10",
            "weight_kg": 40.0,
            "session_id": session_id,
        },
    ).json()

    # Eliminar serie 2
    del_res = api.delete(f"{ASSIGNED_PATH}/workout-logs/{log2['id']}", headers=student)
    assert del_res.status_code == 204

    with sessions() as db:
        pr = db.scalar(select(PersonalRecord).where(PersonalRecord.exercise_id == ex1_id))
        assert pr is not None
        assert float(pr.weight_kg) == 60.0
        assert pr.workout_set_log_id == log1["id"]


def test_get_assigned_personal_records_endpoint(client):
    """El endpoint GET /assigned/personal-records devuelve las marcas vigentes del alumno con nombre de ejercicio."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, ex2_id, _, _ = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 85.0,
            "session_id": session_id,
        },
    )
    api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex2_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 45.0,
            "session_id": session_id,
        },
    )

    # Consultar todos los PRs del alumno
    prs_res = api.get(f"{ASSIGNED_PATH}/personal-records", headers=student)
    assert prs_res.status_code == 200
    prs = prs_res.json()
    assert len(prs) == 2
    ex_names = {p["exercise_name"] for p in prs}
    assert "Sentadilla" in ex_names
    assert "Press de banca" in ex_names

    # Filtrar por un ejercicio
    single_res = api.get(f"{ASSIGNED_PATH}/personal-records?exercise_id={ex1_id}", headers=student)
    assert single_res.status_code == 200
    single_prs = single_res.json()
    assert len(single_prs) == 1
    assert single_prs[0]["exercise_id"] == ex1_id
    assert single_prs[0]["weight_kg"] == 85.0


def test_historical_logs_prior_to_feature_sync_accurately(client):
    """Comprueba que registros históricos previos sin fila en personal_records se respeten como base histórica."""
    api, sessions = client
    trainer = register_and_login(api, "trainer_pr@example.com", "TRAINER")
    student = register_and_login(api, "student_pr@example.com", "STUDENT")
    ex1_id, _, rel_id, routine_id = setup_routine_and_exercises(api, sessions, trainer, "student_pr@example.com")

    # Inyectar manualmente un WorkoutSetLog histórico con 80 kg
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        st_profile = db.scalar(select(StudentProfile).where(StudentProfile.first_name == "Juan"))
        historical_log = WorkoutSetLog(
            student_id=st_profile.id,
            relationship_id=rel_id,
            routine_id=routine_id,
            day_name="Día 1",
            exercise_id=ex1_id,
            exercise_name="Sentadilla",
            modality="GYM",
            set_number=1,
            reps_completed="6",
            weight_kg=Decimal("80.00"),
            recorded_at=now,
        )
        db.add(historical_log)
        db.commit()

    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    session_id = session_res.json()["id"]

    # Nueva serie con 70 kg -> No debe ser PR porque históricamente ya levantó 80 kg
    res_under = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "8",
            "weight_kg": 70.0,
            "session_id": session_id,
        },
    )
    assert res_under.status_code == 201
    assert res_under.json()["is_personal_record"] is False

    # Nueva serie con 85 kg -> Supera los 80 kg históricos
    res_over = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": ex1_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "6",
            "weight_kg": 85.0,
            "session_id": session_id,
        },
    )
    assert res_over.status_code == 201
    assert res_over.json()["is_personal_record"] is True
    assert res_over.json()["pr_previous_weight_kg"] == 80.0
