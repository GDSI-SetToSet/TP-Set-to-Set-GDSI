import json
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from google.genai import errors as genai_errors
from sqlalchemy import select

from backend.src.models.assigned_routine import AssignedRoutine
from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.services.ai_routine_adapter import (
    AIRoutineAdapterError,
    GeminiAIRoutineAdapter,
    HeuristicAIRoutineAdapter,
    get_ai_routine_adapter,
    is_valid_reps_format,
)

AI_GENERATE_PATH = "/api/v1/routines/generate-ai"
ACTIVE_STUDENTS_PATH = "/api/v1/trainers/me/active-students"
STUDENT_ASSIGNED_PATH = "/api/v1/students/me/assigned-routine"


@pytest.fixture(autouse=True)
def _isolate_default_ai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garantiza aislamiento determinista: ningún test usa Gemini real aunque exista .env local."""
    monkeypatch.setenv("AI_PROVIDER", "heuristic")
    monkeypatch.delenv("AI_ROUTINE_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


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
        assert "Modelo de IA no disponible" not in resp.json()["detail"]


def _configure_gemini_env(monkeypatch: pytest.MonkeyPatch, model: str = "gemini-3.5-flash-lite") -> None:
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder-value")
    monkeypatch.setenv("GEMINI_MODEL", model)
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "15")


def test_gemini_structured_generation_success_keep_replace_remove(client, monkeypatch):
    """1. Generación exitosa con respuesta estructurada de Gemini (KEEP, REPLACE y REMOVE)."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gemini_ok@example.com", "TRAINER")
    register_and_login(api, "student_gemini_ok@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gemini_ok@example.com",
        "student_gemini_ok@example.com",
        status="ACTIVE",
        goals=["HIPERTROFIA", "FUERZA"],
        protected_zones=["Hombro derecho", "Rodilla izquierda"],
        has_heart_issue=True,
    )

    ex_keep = create_exercise(
        api,
        trainer,
        name="Remo con Barra",
        target_muscle_group="Espalda",
        description="Tracción horizontal para dorsales",
    )
    ex_replace_orig = create_exercise(
        api,
        trainer,
        name="Press Militar",
        target_muscle_group="Hombro",
        description="Press vertical para hombros",
    )
    ex_remove_orig = create_exercise(
        api,
        trainer,
        name="Sentadilla Libre",
        target_muscle_group="Piernas",
        description="Flexión de rodilla y cadera",
    )
    ex_safe_sub = create_exercise(
        api,
        trainer,
        name="Press de Banca Plano",
        target_muscle_group="Pecho",
        description="Empuje horizontal para pectorales",
    )

    template = create_template(
        api,
        trainer,
        [ex_keep, ex_replace_orig, ex_remove_orig],
        name="Rutina Full Body Base",
        intensity="EXIGENTE",
    )

    gemini_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Se adaptó el volumen a hipertrofia y se protegieron hombro y rodilla.",
        "days": [
            {
                "name": "Día 1 - Adaptado con IA",
                "blocks": [
                    {
                        "name": "Bloque Principal",
                        "exercises": [
                            {
                                "original_exercise_id": ex_keep,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 4,
                                "reps": "8-10",
                                "rest_seconds": 90,
                                "reason": "Ejercicio de tracción seguro para las zonas protegidas.",
                            },
                            {
                                "original_exercise_id": ex_replace_orig,
                                "action": "REPLACE",
                                "replacement_exercise_id": ex_safe_sub,
                                "sets": 3,
                                "reps": "10-12",
                                "rest_seconds": 75,
                                "reason": "Se reemplaza empuje vertical por horizontal para cuidar hombro derecho.",
                            },
                            {
                                "original_exercise_id": ex_remove_orig,
                                "action": "REMOVE",
                                "replacement_exercise_id": None,
                                "sets": None,
                                "reps": None,
                                "rest_seconds": None,
                                "reason": "Eliminado por impacto sobre rodilla izquierda sin sustituto de tren inferior.",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(gemini_payload),
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING_REVIEW"
    assert data["intensity"] == "MEDIA"
    assert data["exercise_count"] == 2
    assert "Google Gemini (gemini-3.5-flash-lite)" in data["adaptation_summary"]
    assert "[REMOVE] Eliminado 'Sentadilla Libre'" in data["adaptation_summary"]

    exercises_out = data["days"][0]["blocks"][0]["exercises"]
    assert len(exercises_out) == 2
    assert exercises_out[0]["exercise"]["id"] == ex_keep
    assert exercises_out[0]["sets"] == 4
    assert exercises_out[0]["reps"] == "8-10"
    assert "[KEEP]" in exercises_out[0]["adaptation_notes"]

    assert exercises_out[1]["exercise"]["id"] == ex_safe_sub
    assert exercises_out[1]["sets"] == 3
    assert exercises_out[1]["reps"] == "10-12"
    assert "[REPLACE]" in exercises_out[1]["adaptation_notes"]

    # Verificar que el prompt enviado a Gemini NO filtró correo ni teléfono del alumno
    called_kwargs = mock_client.models.generate_content.call_args.kwargs
    sent_contents = called_kwargs["contents"]
    assert "student_gemini_ok@example.com" not in sent_contents
    assert ex_keep in sent_contents
    assert ex_safe_sub in sent_contents


def test_gemini_authentication_error(client, monkeypatch):
    """2. Error de autenticación con Gemini."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gemini_auth@example.com", "TRAINER")
    register_and_login(api, "student_gemini_auth@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gemini_auth@example.com",
        "student_gemini_auth@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.ClientError(
        400,
        {"error": {"message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}},
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "autenticación" in detail.lower()
    assert "test-only-placeholder-value" not in detail


def test_gemini_quota_exhausted_429(client, monkeypatch):
    """3. Cuota agotada (429) en Gemini sin fallback silencioso."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gemini_429@example.com", "TRAINER")
    register_and_login(api, "student_gemini_429@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gemini_429@example.com",
        "student_gemini_429@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.ClientError(
        429,
        {"error": {"message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}},
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 429
    assert "cuota" in resp.json()["detail"].lower()

    # Verificar que no se creó ninguna rutina en la base de datos
    with sessions() as db:
        routines = db.scalars(select(AssignedRoutine).where(AssignedRoutine.student_id == student_id)).all()
        assert len(routines) == 0


def test_gemini_timeout_error(client, monkeypatch):
    """4. Timeout al consultar Gemini."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gemini_timeout@example.com", "TRAINER")
    register_and_login(api, "student_gemini_timeout@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gemini_timeout@example.com",
        "student_gemini_timeout@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = httpx.ReadTimeout("Timed out waiting for Gemini")

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 504
    assert "tiempo de espera" in resp.json()["detail"].lower()


def test_gemini_invalid_json_response(client, monkeypatch):
    """5. Respuesta JSON inválida o malformada desde Gemini."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gemini_json@example.com", "TRAINER")
    register_and_login(api, "student_gemini_json@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gemini_json@example.com",
        "student_gemini_json@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text="{invalid_json: true, unclosed",
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 502
    assert "json" in resp.json()["detail"].lower()


def test_gemini_nonexistent_substitute_exercise_rejected(client, monkeypatch):
    """6. Ejercicio sustituto inexistente o fuera del catálogo permitido."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gemini_sub@example.com", "TRAINER")
    register_and_login(api, "student_gemini_sub@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gemini_sub@example.com",
        "student_gemini_sub@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Press Militar", target_muscle_group="Hombro")
    template = create_template(api, trainer, [ex])

    invalid_sub_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Intento de sustitución por ID inventado.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex,
                                "action": "REPLACE",
                                "replacement_exercise_id": "id-inventado-por-alucinacion-999",
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Reemplazo inválido.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(invalid_sub_payload),
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 502
    assert "sustituto inexistente" in resp.json()["detail"].lower()


def test_gemini_out_of_range_parameters_rejected(client, monkeypatch):
    """7. Parámetros fuera de rango (series, descanso, repeticiones o intensidad)."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gemini_range@example.com", "TRAINER")
    register_and_login(api, "student_gemini_range@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gemini_range@example.com",
        "student_gemini_range@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    out_of_range_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Series fuera de rango.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 45,  # Máximo permitido es 20
                                "reps": "10-12",
                                "rest_seconds": 60,
                                "reason": "Volumen excesivo.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(out_of_range_payload),
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 502
    assert "fuera de rango" in resp.json()["detail"].lower()


def test_provider_selection_via_configuration(client, monkeypatch):
    """8. Selección del proveedor mediante configuración y detección de falta de API Key."""
    monkeypatch.setenv("AI_PROVIDER", "heuristic")
    assert isinstance(get_ai_routine_adapter(), HeuristicAIRoutineAdapter)

    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    adapter = get_ai_routine_adapter()
    assert isinstance(adapter, GeminiAIRoutineAdapter)
    assert adapter.model == "gemini-3.5-flash-lite"

    # Proveedor inválido lanza error controlado
    monkeypatch.setenv("AI_PROVIDER", "invalid_provider")
    with pytest.raises(AIRoutineAdapterError) as exc_info:
        get_ai_routine_adapter()
    assert exc_info.value.status_code == 500

    # Si AI_PROVIDER=gemini pero falta GEMINI_API_KEY, el endpoint devuelve 503 comprensible
    api, sessions = client
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    trainer = register_and_login(api, "coach_nokey@example.com", "TRAINER")
    register_and_login(api, "student_nokey@example.com", "STUDENT")
    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_nokey@example.com",
        "student_nokey@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    resp = api.post(
        AI_GENERATE_PATH,
        headers=trainer,
        json={"student_id": student_id, "template_id": template["id"]},
    )
    assert resp.status_code == 503
    assert "no está configurado" in resp.json()["detail"].lower()


def test_explicit_heuristic_fallback_after_gemini_failure(client, monkeypatch):
    """9. Fallback heurístico explícito cuando Gemini falla o agota su cuota."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_fallback@example.com", "TRAINER")
    register_and_login(api, "student_fallback@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_fallback@example.com",
        "student_fallback@example.com",
        status="ACTIVE",
        goals=["HIPERTROFIA"],
    )
    ex = create_exercise(api, trainer, name="Press de Banca", target_muscle_group="Pecho")
    template = create_template(api, trainer, [ex])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = genai_errors.ClientError(
        429,
        {"error": {"message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}},
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        # 1) Intento con proveedor por defecto (gemini) falla con 429 sin cambiar silenciosamente
        fail_resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )
        assert fail_resp.status_code == 429

        # 2) El entrenador solicita explícitamente usar el modo heurístico ('provider': 'heuristic')
        fallback_resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={
                "student_id": student_id,
                "template_id": template["id"],
                "provider": "heuristic",
            },
        )
        assert fallback_resp.status_code == 201
        data = fallback_resp.json()
        assert data["status"] == "PENDING_REVIEW"
        assert "Adaptador Heurístico" in data["adaptation_summary"]


def test_gemini_persistence_template_immutability_and_approval_flow(client, monkeypatch):
    """10, 11 y 12. Persistencia PENDING_REVIEW, conservación de plantilla original y aprobación con Gemini."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_gem_flow@example.com", "TRAINER")
    student = register_and_login(api, "student_gem_flow@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_gem_flow@example.com",
        "student_gem_flow@example.com",
        status="ACTIVE",
        goals=["FUERZA"],
    )

    ex = create_exercise(api, trainer, name="Peso Muerto Rumano", target_muscle_group="Piernas")
    template = create_template(
        api,
        trainer,
        [ex],
        name="Plantilla Fuerza Original",
        duration_weeks=6,
        intensity="ALTA",
    )

    gemini_payload = {
        "intensity": "EXIGENTE",
        "adaptation_summary": "Aumento de carga progresiva orientado a fuerza máxima.",
        "days": [
            {
                "name": "Día 1 - Fuerza",
                "blocks": [
                    {
                        "name": "Bloque Principal",
                        "exercises": [
                            {
                                "original_exercise_id": ex,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 5,
                                "reps": "5",
                                "rest_seconds": 180,
                                "reason": "Progresión de fuerza 5x5.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(gemini_payload),
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        gen_resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert gen_resp.status_code == 201
    created = gen_resp.json()
    routine_id = created["id"]

    # (10) Persistencia en PENDING_REVIEW y bloqueo de acceso al alumno antes de aprobación
    assert created["status"] == "PENDING_REVIEW"
    assert created["approved_at"] is None
    assert api.get(STUDENT_ASSIGNED_PATH, headers=student).json() is None
    assert api.get(f"/api/v1/routines/assigned/{routine_id}", headers=student).status_code == 403

    # (11) Conservación intacta de la rutina genérica original en la biblioteca
    tpl_resp = api.get(f"/api/v1/routine-templates/{template['id']}", headers=trainer)
    assert tpl_resp.status_code == 200
    tpl_after = tpl_resp.json()
    assert tpl_after["name"] == "Plantilla Fuerza Original"
    assert tpl_after["duration_weeks"] == 6
    assert tpl_after["intensity"] == "ALTA"
    orig_ex_entry = tpl_after["days"][0]["blocks"][0]["exercises"][0]
    assert orig_ex_entry["sets"] == 4
    assert orig_ex_entry["reps"] == "10-12"
    assert orig_ex_entry["rest_seconds"] == 60

    # (12) Aprobación mediante el flujo existente
    approve_resp = api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=trainer)
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "APPROVED"
    assert approved["approved_at"] is not None

    # El alumno ahora puede consultar la rutina aprobada
    st_active = api.get(STUDENT_ASSIGNED_PATH, headers=student)
    assert st_active.status_code == 200
    assert st_active.json()["id"] == routine_id


def test_gemini_incomplete_decisions_rejected(client, monkeypatch):
    """I-2. Rechazar propuesta cuando falta la decisión explícita de algún ejercicio original."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_inc_dec@example.com", "TRAINER")
    register_and_login(api, "student_inc_dec@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_inc_dec@example.com",
        "student_inc_dec@example.com",
        status="ACTIVE",
    )

    ex1 = create_exercise(api, trainer, name="Remo con Barra", target_muscle_group="Espalda")
    ex2 = create_exercise(api, trainer, name="Press de Banca", target_muscle_group="Pecho")
    template = create_template(api, trainer, [ex1, ex2])

    # Gemini solo devuelve decisión para ex1 y omite silenciosamente ex2
    incomplete_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Propuesta incompleta.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex1,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 4,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Se conserva.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(incomplete_payload),
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 502
    assert "incompleta" in resp.json()["detail"].lower()


def test_gemini_duplicate_or_contradictory_decisions_rejected(client, monkeypatch):
    """I-3. Rechazar propuesta con dos decisiones o decisiones contradictorias para el mismo original_exercise_id."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_dup_dec@example.com", "TRAINER")
    register_and_login(api, "student_dup_dec@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_dup_dec@example.com",
        "student_dup_dec@example.com",
        status="ACTIVE",
    )

    ex1 = create_exercise(api, trainer, name="Remo con Barra", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex1])

    contradictory_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Decisiones contradictorias.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex1,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 4,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Se conserva.",
                            },
                            {
                                "original_exercise_id": ex1,
                                "action": "REMOVE",
                                "replacement_exercise_id": None,
                                "sets": None,
                                "reps": None,
                                "rest_seconds": None,
                                "reason": "Se elimina simultáneamente.",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(contradictory_payload),
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 502
    assert "duplicadas o contradictorias" in resp.json()["detail"].lower()


def test_gemini_duplicate_exercises_in_block_or_kept_collision_rejected(client, monkeypatch):
    """I-3. Rechazar reemplazos que dupliquen ejercicios ya conservados o ejercicios duplicados en un bloque."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_dup_blk@example.com", "TRAINER")
    register_and_login(api, "student_dup_blk@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_dup_blk@example.com",
        "student_dup_blk@example.com",
        status="ACTIVE",
    )

    ex1 = create_exercise(api, trainer, name="Remo con Barra", target_muscle_group="Espalda")
    ex2 = create_exercise(api, trainer, name="Press Militar", target_muscle_group="Hombro")
    ex_sub = create_exercise(api, trainer, name="Press de Banca", target_muscle_group="Pecho")
    template = create_template(api, trainer, [ex1, ex2])

    # Caso A: Reemplazar ex2 por ex1 (que ya fue conservado con KEEP)
    collision_with_kept_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Reemplazo colisiona con ejercicio conservado.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex1,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 4,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Conservado.",
                            },
                            {
                                "original_exercise_id": ex2,
                                "action": "REPLACE",
                                "replacement_exercise_id": ex1,
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Sustituido por el mismo ejercicio conservado.",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    # Caso B: Ambos ejercicios reemplazados por el mismo sustituto ex_sub dentro del mismo bloque
    duplicate_in_block_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Dos reemplazos hacia el mismo ejercicio en el bloque.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex1,
                                "action": "REPLACE",
                                "replacement_exercise_id": ex_sub,
                                "sets": 4,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Reemplazo 1.",
                            },
                            {
                                "original_exercise_id": ex2,
                                "action": "REPLACE",
                                "replacement_exercise_id": ex_sub,
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Reemplazo 2 duplicado en el bloque.",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    for bad_payload in (collision_with_kept_payload, duplicate_in_block_payload):
        mock_client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps(bad_payload),
            parsed=None,
        )
        with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
            resp = api.post(
                AI_GENERATE_PATH,
                headers=trainer,
                json={"student_id": student_id, "template_id": template["id"]},
            )
        assert resp.status_code == 502
        assert "duplicado" in resp.json()["detail"].lower()


@pytest.mark.parametrize(
    "valid_reps",
    ["10", "8-12", "12 c/l", "15 por lado", "10 min", "5-6"],
)
def test_valid_reps_semantic_formats_accepted(client, monkeypatch, valid_reps):
    """I-4. Formatos deportivos válidos de repeticiones son aceptados."""
    assert is_valid_reps_format(valid_reps) is True

    api, sessions = client
    _configure_gemini_env(monkeypatch)

    email_suffix = abs(hash(valid_reps)) % 100000
    trainer = register_and_login(api, f"coach_reps_ok_{email_suffix}@example.com", "TRAINER")
    register_and_login(api, f"student_reps_ok_{email_suffix}@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        f"coach_reps_ok_{email_suffix}@example.com",
        f"student_reps_ok_{email_suffix}@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Formato de repeticiones válido.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 3,
                                "reps": valid_reps,
                                "rest_seconds": 60,
                                "reason": "Ajuste válido.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(payload),
        parsed=None,
    )
    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )
    assert resp.status_code == 201
    assert resp.json()["days"][0]["blocks"][0]["exercises"][0]["reps"] == valid_reps


@pytest.mark.parametrize(
    "invalid_reps",
    ["0", "-5", "9999", "muchas", "12-8", "0-10", ""],
)
def test_invalid_reps_semantic_formats_rejected(client, monkeypatch, invalid_reps):
    """I-4. Formatos inválidos de repeticiones ('0', '-5', '9999', 'muchas', etc.) son rechazados."""
    assert is_valid_reps_format(invalid_reps) is False

    api, sessions = client
    _configure_gemini_env(monkeypatch)

    email_suffix = abs(hash(invalid_reps)) % 100000
    trainer = register_and_login(api, f"coach_reps_bad_{email_suffix}@example.com", "TRAINER")
    register_and_login(api, f"student_reps_bad_{email_suffix}@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        f"coach_reps_bad_{email_suffix}@example.com",
        f"student_reps_bad_{email_suffix}@example.com",
        status="ACTIVE",
    )
    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Formato de repeticiones inválido.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 3,
                                "reps": invalid_reps,
                                "rest_seconds": 60,
                                "reason": "Ajuste inválido.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(payload),
        parsed=None,
    )
    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )
    assert resp.status_code == 502
    assert "repeticiones" in resp.json()["detail"].lower()


def test_gemini_prompt_catalog_excludes_protected_zone_conflicts(client, monkeypatch):
    """M-2. El catálogo enviado en el prompt a Gemini excluye ejercicios que comprometen zonas protegidas."""
    api, sessions = client
    _configure_gemini_env(monkeypatch)

    trainer = register_and_login(api, "coach_cat_filter@example.com", "TRAINER")
    register_and_login(api, "student_cat_filter@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_cat_filter@example.com",
        "student_cat_filter@example.com",
        status="ACTIVE",
        protected_zones=["Hombro derecho"],
    )

    ex_safe = create_exercise(
        api,
        trainer,
        name="Remo con Barra",
        target_muscle_group="Espalda",
        description="Tracción horizontal para dorsales",
    )
    ex_unsafe_catalog = create_exercise(
        api,
        trainer,
        name="Vuelos Laterales de Hombro",
        target_muscle_group="Hombro",
        description="Abducción de hombro",
    )
    template = create_template(api, trainer, [ex_safe])

    gemini_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Adaptada.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": ex_safe,
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Seguro.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(
        text=json.dumps(gemini_payload),
        parsed=None,
    )

    with patch("backend.src.services.ai_routine_adapter.genai.Client", return_value=mock_client):
        resp = api.post(
            AI_GENERATE_PATH,
            headers=trainer,
            json={"student_id": student_id, "template_id": template["id"]},
        )

    assert resp.status_code == 201
    sent_contents = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert ex_safe in sent_contents
    assert ex_unsafe_catalog not in sent_contents


def test_approve_routine_requires_active_relationship_and_author(client):
    """M-3. Aprobar una rutina exige que el vínculo entrenador-alumno siga ACTIVE y que sea el entrenador autor."""
    api, sessions = client
    trainer = register_and_login(api, "coach_appr_rel@example.com", "TRAINER")
    other_trainer = register_and_login(api, "coach_other_appr@example.com", "TRAINER")
    register_and_login(api, "student_appr_rel@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_appr_rel@example.com",
        "student_appr_rel@example.com",
        status="ACTIVE",
    )

    ex = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    template = create_template(api, trainer, [ex])

    gen_resp = api.post(
        AI_GENERATE_PATH,
        headers=trainer,
        json={"student_id": student_id, "template_id": template["id"]},
    )
    assert gen_resp.status_code == 201
    routine_id = gen_resp.json()["id"]

    # Otro entrenador no puede aprobar la propuesta
    other_resp = api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=other_trainer)
    assert other_resp.status_code == 403

    # Si el vínculo pasa a estado TERMINATED antes de aprobar, el entrenador tampoco puede aprobarla
    with sessions() as db:
        rel = db.scalar(select(TrainingRelationship).where(TrainingRelationship.student_id == student_id))
        rel.status = "TERMINATED"
        db.commit()

    inactive_resp = api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=trainer)
    assert inactive_resp.status_code == 403
    assert "vínculo activo" in inactive_resp.json()["detail"].lower()


