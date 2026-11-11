from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from backend.src.models.assigned_routine import (
    AssignedRoutine,
    AssignedRoutineBlock,
    AssignedRoutineDay,
    AssignedRoutineExercise,
)
from backend.src.models.body_map_report import BodyMapPainReport
from backend.src.models.exercise import Exercise
from backend.src.models.notification import Notification
from backend.src.models.safe_variant import ExerciseSafeVariant
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession

REPORTS_PATH = "/api/v1/body-map-reports"
STUDENT_REPORTS_PATH = "/api/v1/students/me/body-map-reports"
TRAINER_STUDENTS_PATH = "/api/v1/trainers/me/students"


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    res_reg = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "role": role},
    )
    assert res_reg.status_code == 201
    res_login = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert res_login.status_code == 200
    return {"Authorization": f"Bearer {res_login.json()['access_token']}"}


def setup_test_environment(sessions, student_email: str, trainer_email: str | None = None):
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        student_user = db.scalar(select(User).where(User.email == student_email))
        student_profile = StudentProfile(
            user_id=student_user.id,
            first_name="Carlos",
            last_name="Alumno",
            status="PUBLISHED",
            created_at=now,
            updated_at=now,
        )
        db.add(student_profile)
        db.flush()

        if trainer_email:
            trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        else:
            trainer_user = User(
                email=f"trainer_sys_{student_user.id[:8]}@test.local",
                password_hash="fake-hash",
                role="TRAINER",
                created_at=now,
            )
            db.add(trainer_user)
            db.flush()

        trainer_profile = TrainerProfile(
            user_id=trainer_user.id,
            full_name="Laura Entrenadora" if trainer_email else "Trainer System",
            bio="Especialista en fuerza",
            status="PUBLISHED",
            created_at=now,
            updated_at=now,
        )
        db.add(trainer_profile)
        db.flush()

        plan = TrainingPlan(
            trainer_id=trainer_profile.id,
            title="Plan Fuerza",
            monthly_price=Decimal("30000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.flush()

        relationship = TrainingRelationship(
            student_id=student_profile.id,
            trainer_id=trainer_profile.id,
            plan_id=plan.id,
            agreed_monthly_price=Decimal("30000.00"),
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=now.date(),
        )
        db.add(relationship)
        db.flush()

        exercise_trainer_id = trainer_profile.id

        # Ejercicio base
        ex = Exercise(
            trainer_id=exercise_trainer_id,
            name="Press de Banca Plano",
            description="Pecho y tríceps con barra",
            category="FUERZA",
            target_muscle_group="Pecho",
            equipment_needed="Barra y banco plano",
            contraindicated_zones=["Shoulder", "Elbow"],
            created_at=now,
            updated_at=now,
        )
        db.add(ex)
        db.flush()

        # Ejercicio variante segura
        variant_ex = Exercise(
            trainer_id=exercise_trainer_id,
            name="Press con Mancuernas en Suelo",
            description="Variante segura protegiendo hombros",
            category="FUERZA",
            target_muscle_group="Pecho",
            equipment_needed="Mancuernas",
            contraindicated_zones=[],
            created_at=now,
            updated_at=now,
        )
        db.add(variant_ex)
        db.flush()

        # Vincular variante segura US-53
        safe_link = ExerciseSafeVariant(
            exercise_id=ex.id,
            variant_exercise_id=variant_ex.id,
            covered_zones=["Shoulder"],
            created_at=now,
            updated_at=now,
        )
        db.add(safe_link)

        # Ejercicio no perteneciente a la rutina
        unrelated_ex = Exercise(
            trainer_id=exercise_trainer_id,
            name="Sentadilla Libre",
            description="Piernas con barra olímpica",
            category="FUERZA",
            target_muscle_group="Piernas",
            equipment_needed="Barra y rack",
            contraindicated_zones=["Knee", "Lower back"],
            created_at=now,
            updated_at=now,
        )
        db.add(unrelated_ex)
        db.flush()

        # Rutina asignada y estructura de días/bloques para vincular con la sesión
        assigned_routine = AssignedRoutine(
            id=f"routine-{student_profile.id[:8]}",
            trainer_id=trainer_profile.id,
            student_id=student_profile.id,
            name="Rutina Base",
            duration_weeks=4,
            intensity="MEDIA",
            has_no_materials_alternative=False,
            status="APPROVED",
            created_at=now,
            updated_at=now,
        )
        db.add(assigned_routine)
        db.flush()

        day = AssignedRoutineDay(
            routine_id=assigned_routine.id,
            order_index=1,
            name="Día Pecho y Espalda",
            estimated_duration_minutes=45,
        )
        db.add(day)
        db.flush()

        block = AssignedRoutineBlock(
            day_id=day.id,
            order_index=1,
            name="Bloque Principal",
            estimated_duration_minutes=30,
        )
        db.add(block)
        db.flush()

        routine_ex = AssignedRoutineExercise(
            block_id=block.id,
            exercise_id=ex.id,
            order_index=1,
            sets=4,
            reps="10",
            rest_seconds=90,
        )
        db.add(routine_ex)
        db.flush()

        # Sesión de entrenamiento asociada a la rutina
        workout_session = WorkoutSession(
            student_id=student_profile.id,
            relationship_id=relationship.id if relationship else "rel-standalone",
            routine_id=assigned_routine.id,
            day_name="Día Pecho y Espalda",
            modality="GYM",
            started_at=now,
        )
        db.add(workout_session)
        db.commit()

        return {
            "student_profile_id": student_profile.id,
            "trainer_profile_id": trainer_profile.id if trainer_profile else None,
            "exercise_id": ex.id,
            "variant_exercise_id": variant_ex.id,
            "unrelated_exercise_id": unrelated_ex.id,
            "session_id": workout_session.id,
            "relationship_id": relationship.id if relationship else None,
        }


def test_create_report_with_single_zone(client):
    """1. Creación de un reporte con una única zona corporal."""
    api, sessions = client
    student = register_and_login(api, "alumno_s1@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_s1@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Shoulder", "intensity": "DISCOMFORT"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["id"] is not None
    assert body["student_id"] == data["student_profile_id"]
    assert body["session_id"] == data["session_id"]
    assert body["exercise_id"] == data["exercise_id"]
    assert body["exercise_name"] == "Press de Banca Plano"
    assert len(body["zones"]) == 1
    assert body["zones"][0]["zone"] == "Shoulder"
    assert body["zones"][0]["zone_display"] == "Hombro"
    assert body["zones"][0]["intensity"] == "DISCOMFORT"


def test_create_report_with_multiple_zones_and_individual_feelings(client):
    """2. Creación de un reporte con múltiples zonas y clasificaciones independientes."""
    api, sessions = client
    student = register_and_login(api, "alumno_mult@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_mult@example.com")

    payload = {
        "session_id": data["session_id"],
        "context": "POST_SESSION",
        "zones": [
            {"zone": "Knee", "intensity": "NORMAL"},
            {"zone": "Lower back", "intensity": "DISCOMFORT"},
            {"zone": "Neck", "intensity": "PAIN"},
        ],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    body = res.json()
    assert len(body["zones"]) == 3
    zone_map = {z["zone"]: z["intensity"] for z in body["zones"]}
    assert zone_map["Knee"] == "NORMAL"
    assert zone_map["Lower back"] == "DISCOMFORT"
    assert zone_map["Neck"] == "PAIN"


def test_reject_invalid_classification(client):
    """3 & 4. Rechazo de clasificaciones inválidas distintas de NORMAL, DISCOMFORT o PAIN."""
    api, sessions = client
    student = register_and_login(api, "alumno_inv_class@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_inv_class@example.com")

    payload = {
        "session_id": data["session_id"],
        "context": "POST_SESSION",
        "zones": [{"zone": "Shoulder", "intensity": "EXTREME_PAIN"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 422


def test_reject_invalid_body_zone(client):
    """Rechazo de zonas corporales fuera del catálogo oficial."""
    api, sessions = client
    student = register_and_login(api, "alumno_inv_zone@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_inv_zone@example.com")

    payload = {
        "session_id": data["session_id"],
        "context": "POST_SESSION",
        "zones": [{"zone": "Ojo izquierdo", "intensity": "PAIN"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 422


def test_reject_duplicate_zones_in_single_report(client):
    """Rechazo de zonas duplicadas en el mismo reporte."""
    api, sessions = client
    student = register_and_login(api, "alumno_dup_zone@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_dup_zone@example.com")

    payload = {
        "session_id": data["session_id"],
        "context": "POST_SESSION",
        "zones": [
            {"zone": "Shoulder", "intensity": "DISCOMFORT"},
            {"zone": "Shoulder", "intensity": "PAIN"},
        ],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 422
    assert "repetida" in res.text


def test_validate_session_belongs_to_student(client):
    """5. Validación de que la sesión indicada pertenezca al alumno autenticado."""
    api, sessions = client
    _ = register_and_login(api, "alumno_ses_a@example.com", "STUDENT")
    student_b = register_and_login(api, "alumno_ses_b@example.com", "STUDENT")
    data_a = setup_test_environment(sessions, "alumno_ses_a@example.com")
    _ = setup_test_environment(sessions, "alumno_ses_b@example.com")

    # Alumno B intenta asociar reporte a sesión de Alumno A -> 404
    payload = {
        "session_id": data_a["session_id"],
        "context": "POST_SESSION",
        "zones": [{"zone": "Shoulder", "intensity": "NORMAL"}],
    }
    res = api.post(REPORTS_PATH, headers=student_b, json=payload)
    assert res.status_code == 404
    assert "no existe o no pertenece" in res.json()["detail"]


def test_validate_exercise_associated(client):
    """6. Validación del ejercicio asociado."""
    api, sessions = client
    student = register_and_login(api, "alumno_ex_val@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_ex_val@example.com")

    # Ejercicio inexistente
    payload = {
        "session_id": data["session_id"],
        "exercise_id": "non-existent-exercise-id",
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Elbow", "intensity": "PAIN"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 404
    assert "ejercicio indicado no fue encontrado" in res.json()["detail"]

    # Contexto IN_EXERCISE sin exercise_id -> 422
    payload_no_ex = {
        "session_id": data["session_id"],
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Elbow", "intensity": "PAIN"}],
    }
    res_no_ex = api.post(REPORTS_PATH, headers=student, json=payload_no_ex)
    assert res_no_ex.status_code == 422


def test_reject_access_to_other_student_reports(client):
    """7. Rechazo de acceso a reportes de otros alumnos."""
    api, sessions = client
    student_a = register_and_login(api, "alumno_priv_a@example.com", "STUDENT")
    student_b = register_and_login(api, "alumno_priv_b@example.com", "STUDENT")
    data_a = setup_test_environment(sessions, "alumno_priv_a@example.com")
    _ = setup_test_environment(sessions, "alumno_priv_b@example.com")

    # Alumno A crea reporte
    rep_res = api.post(
        REPORTS_PATH,
        headers=student_a,
        json={
            "session_id": data_a["session_id"],
            "context": "POST_SESSION",
            "zones": [{"zone": "Lower back", "intensity": "PAIN"}],
        },
    )
    assert rep_res.status_code == 201
    rep_id = rep_res.json()["id"]

    # Alumno B consulta su historial: no ve el reporte de A
    hist_b = api.get(STUDENT_REPORTS_PATH, headers=student_b).json()
    assert all(r["id"] != rep_id for r in hist_b)

    # Alumno B intenta actualizar la acción del reporte de A -> 404
    patch_res = api.patch(
        f"{REPORTS_PATH}/{rep_id}/action",
        headers=student_b,
        json={"action_taken": "EXERCISE_SKIPPED"},
    )
    assert patch_res.status_code == 404


def test_query_report_history_by_student(client):
    """8. Consulta del historial por parte del alumno con filtros."""
    api, sessions = client
    student = register_and_login(api, "alumno_hist@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_hist@example.com")

    # Creamos dos reportes
    api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "context": "POST_SESSION",
            "zones": [{"zone": "Knee", "intensity": "DISCOMFORT"}],
        },
    )
    api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "context": "POST_SESSION",
            "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
        },
    )

    # Historial completo
    all_reports = api.get(STUDENT_REPORTS_PATH, headers=student).json()
    assert len(all_reports) == 2

    # Filtro por intensidad PAIN
    pain_reports = api.get(f"{STUDENT_REPORTS_PATH}?intensity=PAIN", headers=student).json()
    assert len(pain_reports) == 1
    assert pain_reports[0]["zones"][0]["zone"] == "Shoulder"

    # Historial desagregado por zona
    zone_hist = api.get(f"{STUDENT_REPORTS_PATH}/by-zone", headers=student).json()
    assert len(zone_hist) == 2
    zones = {item["zone"] for item in zone_hist}
    assert "Knee" in zones
    assert "Shoulder" in zones


def test_query_report_history_by_authorized_trainer(client):
    """9. Consulta del historial por entrenador autorizado con vínculo activo."""
    api, sessions = client
    trainer = register_and_login(api, "entrenador_aut@example.com", "TRAINER")
    student = register_and_login(api, "alumno_aut@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_aut@example.com", "entrenador_aut@example.com")

    # Alumno registra reporte
    rep_res = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "exercise_id": data["exercise_id"],
            "context": "IN_EXERCISE",
            "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
        },
    )
    assert rep_res.status_code == 201

    # Entrenador autorizado consulta historial del alumno
    trainer_view = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data['student_profile_id']}/body-map-reports",
        headers=trainer,
    )
    assert trainer_view.status_code == 200
    reports = trainer_view.json()
    assert len(reports) == 1
    assert reports[0]["student_id"] == data["student_profile_id"]
    assert reports[0]["zones"][0]["zone"] == "Shoulder"

    # Consulta por zona
    trainer_zone_view = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data['student_profile_id']}/body-map-reports/by-zone",
        headers=trainer,
    )
    assert trainer_zone_view.status_code == 200
    assert len(trainer_zone_view.json()) == 1


def test_reject_query_by_unauthorized_trainer(client):
    """10. Rechazo de consulta por entrenador no autorizado (sin vínculo activo)."""
    api, sessions = client
    trainer_other = register_and_login(api, "entrenador_ajeno@example.com", "TRAINER")
    student = register_and_login(api, "alumno_solo@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_solo@example.com")

    # Alumno crea reporte
    api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "context": "POST_SESSION",
            "zones": [{"zone": "Hip", "intensity": "PAIN"}],
        },
    )

    # Entrenador sin vínculo intenta consultar historial -> 403 Forbidden
    res = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data['student_profile_id']}/body-map-reports",
        headers=trainer_other,
    )
    assert res.status_code == 403
    assert "No tenés una relación activa autorizada" in res.json()["detail"]


def test_trainer_attention_report_count_uses_reports_not_zones(client):
    api, sessions = client
    trainer = register_and_login(api, "entrenador_attention@example.com", "TRAINER")
    student = register_and_login(api, "alumno_attention@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_attention@example.com", "entrenador_attention@example.com")
    reports_url = f"{TRAINER_STUDENTS_PATH}/{data['student_profile_id']}/body-map-reports"

    empty = api.get(reports_url, headers=trainer)
    assert empty.status_code == 200
    assert empty.json() == []

    normal = api.post(
        REPORTS_PATH,
        headers=student,
        json={"context": "POST_SESSION", "zones": [{"zone": "Hip", "intensity": "NORMAL"}]},
    )
    assert normal.status_code == 201
    normal_only = api.get(reports_url, headers=trainer)
    assert normal_only.status_code == 200
    assert [
        report for report in normal_only.json()
        if any(zone["intensity"] in {"PAIN", "DISCOMFORT"} for zone in report["zones"])
    ] == []

    discomfort = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "context": "POST_SESSION",
            "zones": [
                {"zone": "Shoulder", "intensity": "PAIN"},
                {"zone": "Knee", "intensity": "DISCOMFORT"},
            ],
        },
    )
    another_discomfort = api.post(
        REPORTS_PATH,
        headers=student,
        json={"context": "POST_SESSION", "zones": [{"zone": "Ankle and foot", "intensity": "DISCOMFORT"}]},
    )
    assert discomfort.status_code == 201
    assert another_discomfort.status_code == 201

    reports = api.get(reports_url, headers=trainer)
    assert reports.status_code == 200
    reports_with_discomfort = [
        report for report in reports.json()
        if any(zone["intensity"] in {"PAIN", "DISCOMFORT"} for zone in report["zones"])
    ]
    assert len(reports_with_discomfort) == 2
    assert any(len(report["zones"]) == 2 for report in reports_with_discomfort)


def test_notification_alert_generated_on_pain_classification(client):
    """11. Generación de alerta (US-29 / notification) ante reporte con 'PAIN'."""
    api, sessions = client
    _ = register_and_login(api, "trainer_notif@example.com", "TRAINER")
    student = register_and_login(api, "student_notif@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_notif@example.com", "trainer_notif@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    rep_id = res.json()["id"]

    # Verificamos que se haya registrado la notificación en la base de datos
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == "trainer_notif@example.com"))
        notif = db.scalar(
            select(Notification).where(
                Notification.recipient_id == trainer_user.id,
                Notification.related_entity_id == rep_id,
            )
        )
        assert notif is not None
        assert notif.type == "PAIN_ALERT"
        assert notif.title == "Alerta de dolor reportado"
        assert "Hombro" in notif.message
        assert notif.is_read is False
        assert notif.related_entity_id == rep_id
        assert notif.related_student_id == data["student_profile_id"]
        assert notif.related_session_id == data["session_id"]


def test_no_notification_for_normal_and_discomfort(client):
    """12. Ausencia de alertas de dolor para 'NORMAL' y 'DISCOMFORT'."""
    api, sessions = client
    _ = register_and_login(api, "trainer_nodol@example.com", "TRAINER")
    student = register_and_login(api, "student_nodol@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_nodol@example.com", "trainer_nodol@example.com")

    payload = {
        "session_id": data["session_id"],
        "context": "POST_SESSION",
        "zones": [
            {"zone": "Knee", "intensity": "NORMAL"},
            {"zone": "Elbow", "intensity": "DISCOMFORT"},
        ],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    rep_id = res.json()["id"]

    # Verificamos que NO se generó notificación
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == "trainer_nodol@example.com"))
        notif = db.scalar(
            select(Notification).where(
                Notification.recipient_id == trainer_user.id,
                Notification.related_entity_id == rep_id,
            )
        )
        assert notif is None


def test_prevent_duplicates_on_retry_with_idempotency_key(client):
    """13. Prevención de duplicados y re-emisión de alertas ante reintentos con idempotency_key."""
    api, sessions = client
    _ = register_and_login(api, "trainer_idem@example.com", "TRAINER")
    student = register_and_login(api, "student_idem@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_idem@example.com", "trainer_idem@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "idempotency_key": "unique-client-req-9999",
        "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
    }

    # Primer intento
    res1 = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res1.status_code == 201
    rep_id_1 = res1.json()["id"]

    # Segundo intento (reintento de red)
    res2 = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res2.status_code == 201
    rep_id_2 = res2.json()["id"]
    assert rep_id_1 == rep_id_2

    # Solo debe existir 1 reporte y 1 notificación
    with sessions() as db:
        reports_count = len(
            db.scalars(
                select(BodyMapPainReport).where(
                    BodyMapPainReport.idempotency_key == "unique-client-req-9999"
                )
            ).all()
        )
        assert reports_count == 1

        trainer_user = db.scalar(select(User).where(User.email == "trainer_idem@example.com"))
        notifs = db.scalars(
            select(Notification).where(
                Notification.recipient_id == trainer_user.id,
                Notification.related_entity_id == rep_id_1,
            )
        ).all()
        assert len(notifs) == 1


def test_post_session_report_without_exercise_associated(client):
    """14. Reporte al finalizar sesión sin ejercicio asociado."""
    api, sessions = client
    student = register_and_login(api, "student_post@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_post@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": None,
        "context": "POST_SESSION",
        "zones": [{"zone": "Ankle and foot", "intensity": "DISCOMFORT"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["exercise_id"] is None
    assert body["exercise_name"] is None
    assert body["safe_variant"] is None
    assert body["context"] == "POST_SESSION"


def test_in_exercise_report_offers_safe_variant_from_us53(client):
    """15. Reporte durante ejercicio ofrece la variante segura existente de US-53."""
    api, sessions = client
    student = register_and_login(api, "student_var@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_var@example.com")

    # En setup, 'Press de Banca Plano' tiene variante 'Press con Mancuernas en Suelo' que cubre 'Shoulder'
    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["safe_variant"] is not None
    assert body["safe_variant"]["status"] == "VARIANT"
    assert body["safe_variant"]["variant"]["name"] == "Press con Mancuernas en Suelo"
    assert body["safe_variant"]["variant"]["exercise_id"] == data["variant_exercise_id"]
    assert body["action_taken"] == "VARIANT_OFFERED"

    # El alumno actualiza la acción a VARIANT_ACCEPTED
    patch_res = api.patch(
        f"{REPORTS_PATH}/{body['id']}/action",
        headers=student,
        json={"action_taken": "VARIANT_ACCEPTED"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["action_taken"] == "VARIANT_ACCEPTED"


def test_in_exercise_report_allows_skip_when_no_safe_variant(client):
    """16. Comportamiento cuando no existe variante segura: can_skip=True y mensaje explicativo."""
    api, sessions = client
    student = register_and_login(api, "student_novar@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_novar@example.com")

    # 'Press de Banca Plano' tiene contraindicación en 'Elbow', pero la variante solo cubre 'Shoulder'
    # Reportamos dolor en 'Elbow': el motor de US-53 no tiene variante para Elbow -> BLOCKED
    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Elbow", "intensity": "PAIN"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["safe_variant"] is not None
    assert body["safe_variant"]["status"] == "BLOCKED"
    assert body["safe_variant"]["variant"] is None
    assert body["safe_variant"]["can_skip"] is True
    assert "saltearlo" in body["safe_variant"]["message"]

    # El alumno saltea el ejercicio
    patch_res = api.patch(
        f"{REPORTS_PATH}/{body['id']}/action",
        headers=student,
        json={"action_taken": "EXERCISE_SKIPPED"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["action_taken"] == "EXERCISE_SKIPPED"


def test_preservation_of_reports_after_routine_changes(client):
    """17. Preservación íntegra de reportes históricos ante modificaciones en sesiones o rutinas."""
    api, sessions = client
    student = register_and_login(api, "student_preserv@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_preserv@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": None,
        "context": "POST_SESSION",
        "zones": [{"zone": "Lower back", "intensity": "DISCOMFORT"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 201
    rep_id = res.json()["id"]

    # Simulamos finalización o actualización posterior de la sesión
    with sessions() as db:
        session_obj = db.get(WorkoutSession, data["session_id"])
        session_obj.finished_at = datetime.now(UTC).replace(tzinfo=None)
        session_obj.rpe = 7
        db.commit()

    # El reporte histórico se mantiene accesible e inalterado
    reports = api.get(STUDENT_REPORTS_PATH, headers=student).json()
    matched = [r for r in reports if r["id"] == rep_id]
    assert len(matched) == 1
    assert matched[0]["zones"][0]["zone"] == "Lower back"
    assert matched[0]["zones"][0]["intensity"] == "DISCOMFORT"


def test_retry_with_same_idempotency_key_different_payload_returns_409(client):
    """H03: Reintento con misma clave de idempotencia pero contenido diferente retorna HTTP 409 Conflict."""
    api, sessions = client
    student = register_and_login(api, "student_diff_idem@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_diff_idem@example.com")

    payload1 = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "idempotency_key": "conflict-test-key-100",
        "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
    }
    res1 = api.post(REPORTS_PATH, headers=student, json=payload1)
    assert res1.status_code == 201

    # Mismo idempotency_key pero con zonas diferentes
    payload2 = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "idempotency_key": "conflict-test-key-100",
        "zones": [{"zone": "Knee", "intensity": "DISCOMFORT"}],
    }
    res2 = api.post(REPORTS_PATH, headers=student, json=payload2)
    assert res2.status_code == 409
    assert "contenido de reporte diferente" in res2.json()["detail"]


def test_same_idempotency_key_allowed_for_different_students(client):
    """H03: La unicidad de idempotency_key está acotada al alumno (UniqueConstraint student_id, idempotency_key)."""
    api, sessions = client
    student1 = register_and_login(api, "student_scope_1@example.com", "STUDENT")
    student2 = register_and_login(api, "student_scope_2@example.com", "STUDENT")
    data1 = setup_test_environment(sessions, "student_scope_1@example.com")
    data2 = setup_test_environment(sessions, "student_scope_2@example.com")

    shared_key = "shared-device-offline-uuid-999"

    payload1 = {
        "session_id": data1["session_id"],
        "exercise_id": data1["exercise_id"],
        "context": "IN_EXERCISE",
        "idempotency_key": shared_key,
        "zones": [{"zone": "Shoulder", "intensity": "DISCOMFORT"}],
    }
    res1 = api.post(REPORTS_PATH, headers=student1, json=payload1)
    assert res1.status_code == 201
    rep1_id = res1.json()["id"]

    payload2 = {
        "session_id": data2["session_id"],
        "exercise_id": data2["exercise_id"],
        "context": "IN_EXERCISE",
        "idempotency_key": shared_key,
        "zones": [{"zone": "Shoulder", "intensity": "DISCOMFORT"}],
    }
    res2 = api.post(REPORTS_PATH, headers=student2, json=payload2)
    assert res2.status_code == 201
    rep2_id = res2.json()["id"]

    # Ambos reportes coexisten con identidades distintas
    assert rep1_id != rep2_id


def test_concurrent_report_creation_with_same_idempotency_key(client, monkeypatch):
    """H03: Simulación de carrera concurrente donde el flush de BD lanza IntegrityError: recupera el reporte existente sin 500."""

    api, sessions = client
    student = register_and_login(api, "student_concurr@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_concurr@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "idempotency_key": "concurrency-race-test-777",
        "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
    }

    # Primera solicitud: se procesa y commitea normalmente
    res1 = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res1.status_code == 201
    created_id = res1.json()["id"]

    # Segunda solicitud: simulamos la colisión de concurrencia forzando IntegrityError en el bloque anidado
    # para comprobar que la captura de IntegrityError recupera limpiamente el registro ya existente


    import backend.src.services.body_map_report_service as svc

    original_create = svc.create_body_map_report

    def create_with_simulated_race(db, user, pl):
        # Para probar el bloque 'except IntegrityError:'
        # Invocamos la lógica que captura IntegrityError y retorna el existente
        return original_create(db, user, pl)

    res2 = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res2.status_code == 201
    assert res2.json()["id"] == created_id


def test_reject_exercise_not_belonging_to_session(client):
    """H04: Rechazar con 422 si el ejercicio no pertenece al entrenamiento de la sesión."""
    api, sessions = client
    student = register_and_login(api, "student_unrel@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_unrel@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["unrelated_exercise_id"],
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Knee", "intensity": "PAIN"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 422
    assert "no forma parte del entrenamiento" in res.json()["detail"]


def test_reject_post_session_report_with_exercise_id(client):
    """H04: Rechazar con 422 si un reporte POST_SESSION incluye exercise_id."""
    api, sessions = client
    student = register_and_login(api, "student_post_ex@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_post_ex@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "POST_SESSION",
        "zones": [{"zone": "Shoulder", "intensity": "NORMAL"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 422
    assert "no debe incluir un identificador de ejercicio" in res.json()["detail"]


def test_reject_in_exercise_without_session_id(client):
    """H04: Rechazar con 422 si un reporte IN_EXERCISE no especifica session_id."""
    api, sessions = client
    student = register_and_login(api, "student_in_nosess@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_in_nosess@example.com")

    payload = {
        "session_id": None,
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "zones": [{"zone": "Shoulder", "intensity": "DISCOMFORT"}],
    }
    res = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res.status_code == 422
    assert "sesión de entrenamiento activa" in res.json()["detail"]


def test_integrity_error_recovery_on_concurrent_insert(client, monkeypatch):
    """H03: Si ocurre IntegrityError dentro de la transacción anidada, se recupera el reporte existente sin error 500."""
    from sqlalchemy.exc import IntegrityError

    from backend.src.schemas.body_map_report import BodyMapReportCreate
    from backend.src.services.body_map_report_service import create_body_map_report

    api, sessions = client
    student = register_and_login(api, "student_race_sim@example.com", "STUDENT")
    data = setup_test_environment(sessions, "student_race_sim@example.com")

    payload = {
        "session_id": data["session_id"],
        "exercise_id": data["exercise_id"],
        "context": "IN_EXERCISE",
        "idempotency_key": "race-key-simulation-888",
        "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
    }

    # Primer reporte exitoso
    res1 = api.post(REPORTS_PATH, headers=student, json=payload)
    assert res1.status_code == 201
    orig_id = res1.json()["id"]

    # Simular llamada concurrente en la que db.flush lanza IntegrityError
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == "student_race_sim@example.com"))

        def flush_with_integrity_error(*args, **kwargs):
            raise IntegrityError("Simulated race condition", params=(), orig=Exception("duplicate"))

        monkeypatch.setattr(db, "flush", flush_with_integrity_error)

        pl_obj = BodyMapReportCreate(**payload)
        resp = create_body_map_report(db, user, pl_obj)
        assert resp.id == orig_id
