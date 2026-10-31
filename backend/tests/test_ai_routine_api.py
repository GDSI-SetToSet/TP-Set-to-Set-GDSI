from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User

AI_GENERATE_PATH = "/api/v1/routines/generate-ai"
ACTIVE_STUDENTS_PATH = "/api/v1/trainers/me/active-students"
STUDENT_ASSIGNED_PATH = "/api/v1/students/me/assigned-routine"


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_exercise(api, headers, **overrides) -> str:
    payload = {
        "name": "Press Militar",
        "description": "Press vertical para hombros",
        "category": "FUERZA",
        "target_muscle_group": "Hombro",
        "equipment_needed": "Mancuernas",
        **overrides,
    }
    response = api.post("/api/v1/exercises", headers=headers, json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def create_template(api, headers, exercise_ids: list[str], **overrides) -> dict:
    payload = {
        "name": "Fuerza y Torso",
        "duration_weeks": 4,
        "intensity": "EXIGENTE",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {"exercise_id": eid, "sets": 4, "reps": "10-12", "rest_seconds": 60}
                            for eid in exercise_ids
                        ],
                    }
                ],
            }
        ],
        **overrides,
    }
    response = api.post("/api/v1/routine-templates", headers=headers, json=payload)
    assert response.status_code == 201
    return response.json()


def setup_trainer_and_student_relationship(
    sessions,
    trainer_email: str,
    student_email: str,
    status: str = "ACTIVE",
    goals: list[str] | None = None,
    protected_zones: list[str] | None = None,
    has_heart_issue: bool = False,
    birth_date: date | None = None,
) -> tuple[str, str]:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))

        # Trainer Profile
        trainer_prof = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == trainer_user.id))
        if not trainer_prof:
            trainer_prof = TrainerProfile(
                user_id=trainer_user.id,
                full_name="Carlos Entrenador",
                status="PUBLISHED",
                created_at=now,
                updated_at=now,
            )
            db.add(trainer_prof)
            db.flush()

        # Student Profile
        b_dt = datetime(birth_date.year, birth_date.month, birth_date.day, tzinfo=UTC) if birth_date else datetime(1995, 5, 20, tzinfo=UTC)
        student_prof = db.scalar(select(StudentProfile).where(StudentProfile.user_id == student_user.id))
        if not student_prof:
            student_prof = StudentProfile(
                user_id=student_user.id,
                first_name="Valeria",
                last_name="Alumna",
                birth_date=b_dt,
                fitness_goals=goals or ["HIPERTROFIA"],
                status="PUBLISHED",
                created_at=now,
                updated_at=now,
            )
            db.add(student_prof)
            db.flush()
        else:
            student_prof.fitness_goals = goals or ["HIPERTROFIA"]
            student_prof.birth_date = b_dt

        # Protected zones
        student_prof.protected_zones.clear()
        if protected_zones:
            for zone_area in protected_zones:
                student_prof.protected_zones.append(ProtectedZone(body_area=zone_area, created_at=now))

        # Health questionnaire
        if has_heart_issue:
            db.add(
                HealthQuestionnaire(
                    student_id=student_prof.id,
                    has_heart_condition=True,
                    has_chest_pain_activity=True,
                    has_dizziness_or_balance_loss=False,
                    has_bone_joint_problem=False,
                    takes_prescription_meds=True,
                    completed_at=now,
                )
            )

        # Plan & Relationship
        plan = TrainingPlan(
            trainer_id=trainer_prof.id,
            title="Plan Personalizado",
            monthly_price=Decimal("30000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.flush()

        rel = TrainingRelationship(
            student_id=student_prof.id,
            trainer_id=trainer_prof.id,
            plan_id=plan.id,
            agreed_monthly_price=Decimal("30000.00"),
            agreed_currency="ARS",
            status=status,
            start_date=now.date(),
        )
        db.add(rel)
        db.commit()
        return trainer_prof.id, student_prof.id


def test_list_active_students_for_trainer(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer1@example.com", "TRAINER")
    register_and_login(api, "student1@example.com", "STUDENT")

    setup_trainer_and_student_relationship(
        sessions,
        "trainer1@example.com",
        "student1@example.com",
        status="ACTIVE",
        goals=["HIPERTROFIA"],
        protected_zones=["Hombro derecho"],
        birth_date=date(1990, 1, 1),
    )

    response = api.get(ACTIVE_STUDENTS_PATH, headers=trainer)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["full_name"] == "Valeria Alumna"
    assert data[0]["fitness_goals"] == ["HIPERTROFIA"]
    assert data[0]["protected_zones_count"] == 1
    assert data[0]["age"] is not None


def test_generate_ai_routine_proposal_success_and_incompatible_exercise_substitution(client):
    api, sessions = client
    trainer = register_and_login(api, "coach_ai@example.com", "TRAINER")
    register_and_login(api, "valeria@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_ai@example.com",
        "valeria@example.com",
        status="ACTIVE",
        goals=["HIPERTROFIA"],
        protected_zones=["Hombro derecho"],
    )

    # El entrenador crea 2 ejercicios: uno de hombro (incompatible con la zona protegida) y uno de pecho (seguro)
    shoulder_ex = create_exercise(api, trainer, name="Press Militar", target_muscle_group="Hombro", description="Press vertical de hombro")
    chest_ex = create_exercise(api, trainer, name="Press de Banca", target_muscle_group="Pecho", description="Empuje horizontal para pectorales")

    # La plantilla incluye el ejercicio de hombro
    template = create_template(api, trainer, [shoulder_ex], name="Plantilla Hipertrofia")

    # 1. Generar la rutina con IA
    payload = {"student_id": student_id, "template_id": template["id"]}
    resp = api.post(AI_GENERATE_PATH, headers=trainer, json=payload)
    assert resp.status_code == 201
    routine_data = resp.json()

    # 2. Verificar que se generó una propuesta en PENDING_REVIEW (Human-in-the-Loop)
    assert routine_data["status"] == "PENDING_REVIEW"
    assert routine_data["approved_at"] is None
    assert routine_data["name"] == "Plantilla Hipertrofia - Adaptada para Valeria Alumna"

    # 3. Comprobar que el ejercicio de hombro fue sustituido por el de pecho para proteger el hombro
    adapted_ex = routine_data["days"][0]["blocks"][0]["exercises"][0]
    assert adapted_ex["exercise"]["id"] == chest_ex
    assert "Hombro derecho" in adapted_ex["adaptation_notes"]
    assert "Hombro derecho" in routine_data["adaptation_summary"]

    # 4. Comprobar adaptación de repeticiones a rango de hipertrofia
    assert adapted_ex["reps"] == "8-12"

    # 5. Comprobar que la plantilla genérica original permanece intacta
    with sessions() as db:
        original_template = db.get(RoutineTemplate, template["id"])
        assert original_template.intensity == "EXIGENTE"
        orig_exercises = [e.exercise_id for d in original_template.days for b in d.blocks for e in b.exercises]
        assert orig_exercises == [shoulder_ex]


def test_incompatible_exercise_eliminated_when_no_alternative(client):
    api, sessions = client
    trainer = register_and_login(api, "coach_elim@example.com", "TRAINER")
    register_and_login(api, "student_elim@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_elim@example.com",
        "student_elim@example.com",
        status="ACTIVE",
        goals=["FUERZA"],
        protected_zones=["Rodilla izquierda"],
    )

    # Solo 1 ejercicio en toda la biblioteca del entrenador: Sentadilla (afecta rodilla)
    knee_ex = create_exercise(api, trainer, name="Sentadilla Profunda", target_muscle_group="Piernas")
    template = create_template(api, trainer, [knee_ex], name="Plantilla Piernas")

    # Generar con IA
    resp = api.post(AI_GENERATE_PATH, headers=trainer, json={"student_id": student_id, "template_id": template["id"]})
    assert resp.status_code == 201
    data = resp.json()

    # Como no hay alternativa segura, el ejercicio fue eliminado
    assert data["exercise_count"] == 0
    assert "Eliminado" in data["adaptation_summary"]
    assert "Rodilla izquierda" in data["adaptation_summary"]


def test_health_questionnaire_reduces_intensity_and_adjusts_rest(client):
    api, sessions = client
    trainer = register_and_login(api, "coach_health@example.com", "TRAINER")
    register_and_login(api, "student_health@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_health@example.com",
        "student_health@example.com",
        status="ACTIVE",
        goals=["RESISTENCIA"],
        protected_zones=[],
        has_heart_issue=True,
    )

    chest_ex = create_exercise(api, trainer, name="Flexiones de Brazos", target_muscle_group="Pecho")
    template = create_template(api, trainer, [chest_ex], intensity="EXIGENTE")

    resp = api.post(AI_GENERATE_PATH, headers=trainer, json={"student_id": student_id, "template_id": template["id"]})
    assert resp.status_code == 201
    data = resp.json()

    # La intensidad se redujo de EXIGENTE a ALTA por precaución de salud
    assert data["intensity"] == "ALTA"
    assert "salud" in data["adaptation_summary"].lower()
    # Los descansos y series se ajustaron por salud
    adapted_ex = data["days"][0]["blocks"][0]["exercises"][0]
    assert adapted_ex["rest_seconds"] >= 90
    assert adapted_ex["sets"] <= 3


def test_human_in_the_loop_approval_flow_and_student_access(client):
    api, sessions = client
    trainer = register_and_login(api, "coach_hitl@example.com", "TRAINER")
    student = register_and_login(api, "student_hitl@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_hitl@example.com",
        "student_hitl@example.com",
        status="ACTIVE",
    )

    ex = create_exercise(api, trainer, name="Curl Bíceps", target_muscle_group="Brazos")
    template = create_template(api, trainer, [ex])

    # 1. Entrenador genera propuesta con IA
    gen_resp = api.post(AI_GENERATE_PATH, headers=trainer, json={"student_id": student_id, "template_id": template["id"]})
    assert gen_resp.status_code == 201
    routine_id = gen_resp.json()["id"]

    # 2. El alumno NO puede ver la rutina antes de la aprobación
    st_assigned = api.get(STUDENT_ASSIGNED_PATH, headers=student)
    assert st_assigned.status_code == 200
    assert st_assigned.json() is None

    st_detail = api.get(f"/api/v1/routines/assigned/{routine_id}", headers=student)
    assert st_detail.status_code == 403

    # 3. El entrenador revisa el detalle
    tr_detail = api.get(f"/api/v1/routines/assigned/{routine_id}", headers=trainer)
    assert tr_detail.status_code == 200
    assert tr_detail.json()["status"] == "PENDING_REVIEW"

    # 4. El entrenador aprueba explícitamente la rutina
    appr_resp = api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=trainer)
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()
    assert appr_data["status"] == "APPROVED"
    assert appr_data["approved_at"] is not None

    # 5. Re-aprobar produce 409 Conflict
    re_appr = api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=trainer)
    assert re_appr.status_code == 409

    # 6. El alumno ahora sí puede ver su rutina aprobada
    st_active = api.get(STUDENT_ASSIGNED_PATH, headers=student)
    assert st_active.status_code == 200
    assert st_active.json()["id"] == routine_id

    st_detail_after = api.get(f"/api/v1/routines/assigned/{routine_id}", headers=student)
    assert st_detail_after.status_code == 200
    assert st_detail_after.json()["id"] == routine_id

    # 7. TrainingRelationship.initial_routine_id fue actualizado
    with sessions() as db:
        rel = db.scalar(select(TrainingRelationship).where(TrainingRelationship.student_id == student_id))
        assert rel.initial_routine_id == routine_id


def test_cannot_generate_for_unauthorized_student(client):
    api, sessions = client
    register_and_login(api, "trainer_auth@example.com", "TRAINER")
    trainer_intruder = register_and_login(api, "trainer_intruder@example.com", "TRAINER")
    register_and_login(api, "student_priv@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "trainer_auth@example.com",
        "student_priv@example.com",
        status="ACTIVE",
    )

    ex = create_exercise(api, trainer_intruder, name="Ejercicio Intruso", target_muscle_group="Core")
    template_intruder = create_template(api, trainer_intruder, [ex])

    # El entrenador intruso no tiene vínculo activo con la alumna
    resp = api.post(
        AI_GENERATE_PATH,
        headers=trainer_intruder,
        json={"student_id": student_id, "template_id": template_intruder["id"]},
    )
    assert resp.status_code == 403
    assert "vínculo activo" in resp.json()["detail"].lower()


def test_nonexistent_student_or_template_returns_404(client):
    api, _ = client
    trainer = register_and_login(api, "coach_404@example.com", "TRAINER")

    resp1 = api.post(
        AI_GENERATE_PATH,
        headers=trainer,
        json={"student_id": "nonexistent-id", "template_id": "nonexistent-template"},
    )
    assert resp1.status_code == 404


def test_student_cannot_call_generate_ai(client):
    api, _ = client
    student = register_and_login(api, "student_call@example.com", "STUDENT")

    resp = api.post(
        AI_GENERATE_PATH,
        headers=student,
        json={"student_id": "some-id", "template_id": "some-id"},
    )
    assert resp.status_code == 403


def test_ai_adapter_failure_handling(client):
    api, sessions = client
    trainer = register_and_login(api, "coach_err@example.com", "TRAINER")
    register_and_login(api, "student_err@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_err@example.com",
        "student_err@example.com",
        status="ACTIVE",
    )

    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    # Simular fallo en el motor de IA
    with patch("backend.src.services.assigned_routine_service.get_ai_routine_adapter") as mock_adapter:
        mock_instance = mock_adapter.return_value
        mock_instance.generate_adapted_routine.side_effect = RuntimeError("Modelo de IA no disponible")

        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )
        assert resp.status_code == 500
        assert "mecanismo de adaptación con IA" in resp.json()["detail"]
