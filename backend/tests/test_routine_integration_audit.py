"""End-to-End Cross-Feature Integration Audit Tests (AUD-14).

Verifica el ciclo de vida completo de rutinas entre US-09, US-13, US-14 y US-52:
1. Registro y autenticación de Entrenador y Alumno.
2. Configuración de perfil de Alumno y Zonas Protegidas biomecánicas.
3. Cuestionario de salud PAR-Q del Alumno.
4. Publicación de perfil de Entrenador y creación de Plan de Entrenamiento.
5. Solicitud de entrenamiento creada por el Alumno.
6. Aceptación de solicitud por el Entrenador -> TrainingRelationship ACTIVO.
7. Verificación de /students/me/active-plans (vínculo activo sin rutina).
8. Generación de propuesta de rutina con IA (validación biomecánica + preservación de metadatos).
9. Verificación de seguridad y Human-in-the-Loop (alumno no aprueba ni accede prematuramente).
10. Aprobación de la rutina por el Entrenador.
11. Verificación de sincronización automática en StudentRoutine (AUD-01, AUD-02).
12. Verificación de /students/me/active-plans con el nombre real de la rutina asignada (AUD-09).
13. Verificación de asignación visible en /routine-templates/assignments para el Entrenador.
14. Edición de rutina en borrador y confirmación de cambios (AUD-07 sin colisión de logs).
15. Terminación de vínculo y bloqueo estricto de acceso (AUD-06).
"""


import pytest
from sqlalchemy import select

from backend.src.models import (
    RoutineChangeLog,
    StudentRoutine,
    TrainingRelationship,
)


@pytest.fixture(autouse=True)
def _isolate_default_ai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "heuristic")
    monkeypatch.delenv("AI_ROUTINE_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_full_cross_feature_routine_lifecycle_audit(client):
    """Prueba exhaustiva de 15 pasos validando la integración completa y las correcciones AUD-01 a AUD-13."""
    api, sessions = client

    # -------------------------------------------------------------------------
    # Paso 1: Registro y autenticación de Entrenador y Alumno
    # -------------------------------------------------------------------------
    trainer_headers = register_and_login(api, "coach_e2e@example.com", "TRAINER")
    student_headers = register_and_login(api, "student_e2e@example.com", "STUDENT")

    # -------------------------------------------------------------------------
    # Paso 2: Configuración de perfil de Alumno y Zonas Protegidas biomecánicas
    # -------------------------------------------------------------------------
    student_profile_resp = api.put(
        "/api/v1/students/me/profile",
        headers=student_headers,
        json={
            "first_name": "Valentina",
            "last_name": "Ríos",
            "birth_date": "1998-05-12T00:00:00Z",
            "contact_phone": "+5491133334444",
            "fitness_goals": ["fuerza", "salud_general"],
            "personal_motivation": "Entrenar sin dolor articular",
        },
    )
    assert student_profile_resp.status_code == 200
    student_id = student_profile_resp.json()["id"]

    # Registrar zonas protegidas con sinónimos en español (AUD-03)
    zones_resp = api.put(
        "/api/v1/students/me/protected-zones",
        headers=student_headers,
        json={"zones": ["lumbares", "hombro izquierdo"]},
    )
    assert zones_resp.status_code == 200
    assert len(zones_resp.json()["zones"]) == 2

    # -------------------------------------------------------------------------
    # Paso 3: Cuestionario de salud PAR-Q del Alumno
    # -------------------------------------------------------------------------
    hq_resp = api.post(
        "/api/v1/students/me/health-questionnaire",
        headers=student_headers,
        json={
            "has_heart_condition": False,
            "has_chest_pain_activity": False,
            "has_dizziness_or_balance_loss": False,
            "has_bone_joint_problem": True,
            "takes_prescription_meds": False,
            "other_medical_conditions": "Molestia leve en zona lumbar y hombro",
        },
    )
    assert hq_resp.status_code in (200, 201)

    # -------------------------------------------------------------------------
    # Paso 4: Publicación de perfil de Entrenador y creación de Plan
    # -------------------------------------------------------------------------
    trainer_profile_resp = api.put(
        "/api/v1/trainers/me/profile",
        headers=trainer_headers,
        json={
            "full_name": "Marcos Giménez",
            "contact_phone": "+5491144445555",
            "specialty": "Fuerza y Acondicionamiento",
            "bio": "Entrenador especialista en fuerza y readaptación.",
        },
    )
    assert trainer_profile_resp.status_code == 200
    trainer_id = trainer_profile_resp.json()["id"]

    quota_resp = api.patch(
        "/api/v1/trainers/me/quota",
        headers=trainer_headers,
        json={"max_students": 10},
    )
    assert quota_resp.status_code == 200

    plan_resp = api.post(
        "/api/v1/trainers/me/plans",
        headers=trainer_headers,
        json={"title": "Plan Fuerza E2E", "monthly_price": 35000},
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    # -------------------------------------------------------------------------
    # Paso 5: Solicitud de entrenamiento creada por el Alumno
    # -------------------------------------------------------------------------
    req_resp = api.post(
        "/api/v1/matchmaking/requests",
        headers=student_headers,
        json={
            "trainer_id": trainer_id,
            "plan_id": plan_id,
            "student_message": "Hola Marcos, busco entrenar de forma segura.",
        },
    )
    assert req_resp.status_code == 201
    request_id = req_resp.json()["id"]

    # -------------------------------------------------------------------------
    # Paso 6: Aceptación de solicitud por el Entrenador -> TrainingRelationship ACTIVO
    # -------------------------------------------------------------------------
    accept_resp = api.post(
        f"/api/v1/matchmaking/requests/{request_id}/accept",
        headers=trainer_headers,
        json={"welcome_message": "¡Bienvenida Valentina! Vamos a armar tu rutina."},
    )
    assert accept_resp.status_code == 200
    relationship = accept_resp.json()
    rel_id = relationship["id"]
    assert relationship["status"] == "ACTIVE"

    # -------------------------------------------------------------------------
    # Paso 7: Verificación de /students/me/active-plans (vínculo activo sin rutina aún)
    # -------------------------------------------------------------------------
    active_plans_resp = api.get("/api/v1/students/me/active-plans", headers=student_headers)
    assert active_plans_resp.status_code == 200
    active_plans = active_plans_resp.json()
    assert len(active_plans) >= 1
    current_active_plan = next(p for p in active_plans if p.get("relationship_id") == rel_id)
    assert current_active_plan["has_active_plan"] is True
    assert current_active_plan["routine"] is None

    # -------------------------------------------------------------------------
    # Paso 8: Generación de propuesta de rutina con IA (validación biomecánica + metadatos)
    # -------------------------------------------------------------------------
    # Crear ejercicios para el entrenador:
    # 1. Ejercicio seguro (Sentadilla Goblet con mancuerna, target piernas)
    safe_ex_resp = api.post(
        "/api/v1/exercises",
        headers=trainer_headers,
        json={
            "name": "Sentadilla Goblet",
            "description": "Sentadilla con mancuerna al pecho",
            "category": "FUERZA",
            "target_muscle_group": "Piernas",
            "equipment_needed": "Mancuerna",
            "has_no_materials_alternative": True,
            "contraindicated_zones": [],
        },
    )
    assert safe_ex_resp.status_code == 201
    safe_ex_id = safe_ex_resp.json()["id"]

    # 2. Ejercicio contraindicado para lumbares (Peso Muerto Pesado)
    contra_ex_resp = api.post(
        "/api/v1/exercises",
        headers=trainer_headers,
        json={
            "name": "Peso Muerto Convencional",
            "description": "Levantamiento desde el suelo",
            "category": "FUERZA",
            "target_muscle_group": "Espalda",
            "equipment_needed": "Barra",
            "has_no_materials_alternative": True,
            "contraindicated_zones": ["lower back"],  # Sinónimo en inglés de "lumbares"
        },
    )
    assert contra_ex_resp.status_code == 201
    contra_ex_id = contra_ex_resp.json()["id"]

    # Crear plantilla base con ambos ejercicios y metadatos explícitos
    template_resp = api.post(
        "/api/v1/routine-templates",
        headers=trainer_headers,
        json={
            "name": "Plantilla Base Fuerza E2E",
            "duration_weeks": 4,
            "intensity": "ALTA",
            "has_no_materials_alternative": True,
            "days": [
                {
                    "name": "Día 1 - Tren Inferior",
                    "blocks": [
                        {
                            "name": "Bloque A",
                            "estimated_duration_minutes": 25,
                            "exercises": [
                                {
                                    "exercise_id": safe_ex_id,
                                    "sets": 3,
                                    "reps": "10-12",
                                    "rest_seconds": 60,
                                    "target_weight_kg": 16.0,
                                },
                                {
                                    "exercise_id": contra_ex_id,
                                    "sets": 3,
                                    "reps": "8",
                                    "rest_seconds": 90,
                                    "target_weight_kg": 50.0,
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert template_resp.status_code == 201
    template_id = template_resp.json()["id"]

    # Generar propuesta de rutina con IA
    gen_resp = api.post(
        "/api/v1/routines/generate-ai",
        headers=trainer_headers,
        json={
            "student_id": student_id,
            "template_id": template_id,
            "provider": "heuristic",
        },
    )
    assert gen_resp.status_code == 201
    proposal = gen_resp.json()
    routine_id = proposal["id"]
    assert proposal["status"] == "PENDING_REVIEW"
    assert proposal["trainer_name"] == "Marcos Giménez"
    assert proposal["has_no_materials_alternative"] is True

    # Comprobar que el ejercicio contraindicado por lumbares fue eliminado/reemplazado (AUD-03)
    proposed_exercises = [
        e["exercise"]["id"]
        for day in proposal["days"]
        for block in day["blocks"]
        for e in block["exercises"]
    ]
    assert contra_ex_id not in proposed_exercises
    assert safe_ex_id in proposed_exercises

    # Comprobar preservación de metadatos (AUD-04, AUD-05)
    first_block = proposal["days"][0]["blocks"][0]
    assert first_block["estimated_duration_minutes"] == 25
    first_ex = next(e for e in first_block["exercises"] if e["exercise"]["id"] == safe_ex_id)
    assert first_ex["target_weight_kg"] == 16.0

    # -------------------------------------------------------------------------
    # Paso 9: Human-in-the-Loop y seguridad de acceso
    # -------------------------------------------------------------------------
    # El alumno NO debe poder consultar la propuesta PENDING directamente (403)
    assert api.get(f"/api/v1/routines/assigned/{routine_id}", headers=student_headers).status_code == 403
    # El alumno NO debe poder aprobar la propuesta (403)
    assert api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=student_headers).status_code == 403

    # -------------------------------------------------------------------------
    # Paso 10: Aprobación de la rutina por el Entrenador
    # -------------------------------------------------------------------------
    approve_resp = api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=trainer_headers)
    assert approve_resp.status_code == 200
    approved_routine = approve_resp.json()
    assert approved_routine["status"] == "APPROVED"

    # Ahora que está aprobada, el alumno SÍ puede ver su rutina asignada
    student_assigned_resp = api.get(f"/api/v1/routines/assigned/{routine_id}", headers=student_headers)
    assert student_assigned_resp.status_code == 200
    assert student_assigned_resp.json()["name"] == proposal["name"]

    # -------------------------------------------------------------------------
    # Paso 11: Verificación de sincronización automática en StudentRoutine (AUD-01, AUD-02)
    # -------------------------------------------------------------------------
    with sessions() as db:
        sr = db.scalar(
            select(StudentRoutine).where(
                StudentRoutine.relationship_id == rel_id,
                StudentRoutine.status == "ACTIVE",
            )
        )
        assert sr is not None, "StudentRoutine no fue sincronizada al aprobar AssignedRoutine"
        assert sr.source_kind == "AI"
        assert sr.name == proposal["name"]
        assert sr.has_no_materials_alternative is True

        db_rel = db.get(TrainingRelationship, rel_id)
        assert db_rel.initial_routine_id == routine_id

    # -------------------------------------------------------------------------
    # Paso 12: Verificación de /students/me/active-plans (nombre real de la rutina, AUD-09)
    # -------------------------------------------------------------------------
    plans_after_approval = api.get("/api/v1/students/me/active-plans", headers=student_headers).json()
    active_plan = next(p for p in plans_after_approval if p.get("relationship_id") == rel_id)
    assert active_plan["routine"] is not None
    assert active_plan["routine"]["name"] == proposal["name"]
    assert active_plan["routine"]["name"] != "Rutina Inicial"
    assert active_plan["routine"]["is_available"] is True

    # -------------------------------------------------------------------------
    # Paso 13: Verificación de /routine-templates/assignments para el Entrenador
    # -------------------------------------------------------------------------
    assignments_resp = api.get("/api/v1/routine-templates/assignments", headers=trainer_headers)
    assert assignments_resp.status_code == 200
    assignments = assignments_resp.json()
    student_assignment = next(a for a in assignments if a.get("relationship_id") == rel_id)
    assert student_assignment["routine_name"] == proposal["name"]
    assert student_assignment["routine_template_id"] == routine_id

    # -------------------------------------------------------------------------
    # Paso 14: Edición en borrador y confirmación de cambios (AUD-07)
    # -------------------------------------------------------------------------
    # Crear un nuevo ejercicio seguro sin materiales para agregar a la rutina
    extra_ex_resp = api.post(
        "/api/v1/exercises",
        headers=trainer_headers,
        json={
            "name": "Plancha Abdominal E2E",
            "description": "Isométrico de core sin carga",
            "category": "FUERZA",
            "target_muscle_group": "Abdominales",
            "equipment_needed": "Ninguno",
            "has_no_materials_alternative": True,
            "contraindicated_zones": [],
        },
    )
    assert extra_ex_resp.status_code == 201
    extra_ex_id = extra_ex_resp.json()["id"]

    # Obtener estado actual del borrador del alumno
    student_routine_view = api.get(f"/api/v1/trainers/me/students/{student_id}/routine", headers=trainer_headers)
    assert student_routine_view.status_code == 200
    current_version = student_routine_view.json()["draft_version"]

    # Guardar borrador agregando el nuevo ejercicio y modificando series
    save_draft_resp = api.put(
        f"/api/v1/trainers/me/students/{student_id}/routine/draft",
        headers=trainer_headers,
        json={
            "draft_version": current_version,
            "name": "Rutina Valentina - Modificada",
            "duration_weeks": 6,
            "intensity": "MEDIA",
            "has_no_materials_alternative": True,
            "days": [
                {
                    "name": "Día 1 - Tren Inferior y Core",
                    "blocks": [
                        {
                            "name": "Bloque A",
                            "estimated_duration_minutes": 30,
                            "exercises": [
                                {
                                    "exercise_id": safe_ex_id,
                                    "sets": 4,  # Cambiado de 3 a 4
                                    "reps": "12",
                                    "rest_seconds": 60,
                                    "target_weight_kg": 18.0,
                                },
                                {
                                    "exercise_id": extra_ex_id,
                                    "sets": 3,
                                    "reps": "30s",
                                    "rest_seconds": 45,
                                    "target_weight_kg": None,
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert save_draft_resp.status_code == 200

    # Confirmar borrador
    confirm_resp = api.post(
        f"/api/v1/trainers/me/students/{student_id}/routine/draft/confirm",
        headers=trainer_headers,
    )
    assert confirm_resp.status_code == 200
    confirmed_data = confirm_resp.json()
    assert confirmed_data["routine"]["name"] == "Rutina Valentina - Modificada"
    assert confirmed_data["routine"]["exercise_count"] == 2

    # Verificar que RoutineChangeLog registró los cambios sin colisión de claves (AUD-07)
    with sessions() as db:
        change_logs = list(
            db.scalars(
                select(RoutineChangeLog).where(
                    RoutineChangeLog.student_routine_id == sr.id
                )
            )
        )
        assert len(change_logs) >= 1
        latest_log = change_logs[-1]
        assert extra_ex_id in latest_log.changes.get("added", [])

    # -------------------------------------------------------------------------
    # Paso 15: Terminación de vínculo y bloqueo estricto de acceso (AUD-06)
    # -------------------------------------------------------------------------
    with sessions() as db:
        db_rel = db.get(TrainingRelationship, rel_id)
        db_rel.status = "TERMINATED"
        db.commit()

    # Tras terminar el vínculo:
    # 1. El entrenador no puede ver la rutina asignada (403)
    assert api.get(f"/api/v1/routines/assigned/{routine_id}", headers=trainer_headers).status_code == 403
    # 2. El alumno no puede ver la rutina asignada (403)
    assert api.get(f"/api/v1/routines/assigned/{routine_id}", headers=student_headers).status_code == 403
    # 3. La consulta de planes activos del alumno ya no muestra este vínculo como activo
    active_plans_term = api.get("/api/v1/students/me/active-plans", headers=student_headers).json()
    assert not any(p.get("relationship_id") == rel_id for p in active_plans_term)
