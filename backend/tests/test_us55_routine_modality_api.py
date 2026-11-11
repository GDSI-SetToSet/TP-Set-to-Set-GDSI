"""Tests de integración y aceptación para US-55: Alternancia de rutina entre gimnasio y casa."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from backend.src.models.assigned_routine import (
    AssignedRoutine,
    AssignedRoutineBlock,
    AssignedRoutineDay,
    AssignedRoutineExercise,
)
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User

EXERCISES_PATH = "/api/v1/exercises"
TEMPLATES_PATH = "/api/v1/routine-templates"
STUDENT_TEMPLATES_PATH = "/api/v1/students/me/routine-templates"
ASSIGNED_PATH = f"{STUDENT_TEMPLATES_PATH}/assigned"
MODALITY_PATH = f"{ASSIGNED_PATH}/modality"
WORKOUT_LOGS_PATH = f"{ASSIGNED_PATH}/workout-logs"


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    reg = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123!", "role": role},
    )
    assert reg.status_code == 201
    login = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_exercise(
    api,
    headers: dict[str, str],
    *,
    name: str = "Sentadilla búlgara",
    equipment_needed: str = "Mancuernas",
    has_no_materials_alternative: bool = True,
) -> str:
    resp = api.post(
        EXERCISES_PATH,
        headers=headers,
        json={
            "name": name,
            "description": f"Descripción técnica de {name}",
            "category": "FUERZA",
            "target_muscle_group": "Cuádriceps",
            "equipment_needed": equipment_needed,
            "has_no_materials_alternative": has_no_materials_alternative,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def entry(
    exercise_id: str,
    sets: int = 3,
    reps: str = "10",
    rest_seconds: int = 60,
    target_weight_kg: float | None = 20.0,
) -> dict:
    return {
        "exercise_id": exercise_id,
        "sets": sets,
        "reps": reps,
        "rest_seconds": rest_seconds,
        "target_weight_kg": target_weight_kg,
    }


def create_template(
    api,
    headers: dict[str, str],
    *exercise_ids: str,
    name: str = "Rutina Full Body",
    has_no_materials_alternative: bool = False,
    days: list[dict] | None = None,
) -> dict:
    payload = {
        "name": name,
        "duration_weeks": 4,
        "intensity": "MEDIA",
        "has_no_materials_alternative": has_no_materials_alternative,
        "days": days
        or [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Principal",
                        "estimated_duration_minutes": 25,
                        "exercises": [entry(ex_id) for ex_id in exercise_ids],
                    }
                ],
            }
        ],
    }
    resp = api.post(TEMPLATES_PATH, headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def link_student(sessions, trainer_email: str, student_email: str, status: str = "ACTIVE") -> str:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))
        trainer_profile = trainer_user.trainer_profile
        if trainer_profile is None:
            trainer_profile = TrainerProfile(user_id=trainer_user.id, created_at=now, updated_at=now)
            db.add(trainer_profile)
            db.flush()
        profile = StudentProfile(user_id=student_user.id, status="PUBLISHED", created_at=now, updated_at=now)
        plan = TrainingPlan(
            trainer_id=trainer_profile.id,
            title="Plan Base",
            monthly_price=Decimal("25000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add_all([profile, plan])
        db.flush()
        rel = TrainingRelationship(
            student_id=profile.id,
            trainer_id=trainer_profile.id,
            plan_id=plan.id,
            agreed_monthly_price=Decimal("25000.00"),
            agreed_currency="ARS",
            status=status,
            start_date=now.date(),
        )
        db.add(rel)
        db.flush()
        rel_id = rel.id
        db.commit()
        return rel_id


def test_us55_ca1_alternation_between_gym_and_home_updates_modality_and_exercises(client):
    """CA-1: El alumno puede alternar entre Gimnasio y Casa/Viaje cuando todos los ejercicios tienen alternativa."""
    api, sessions = client
    trainer = register_and_login(api, "coach@us55.com", "TRAINER")
    student = register_and_login(api, "student@us55.com", "STUDENT")

    squat_id = create_exercise(
        api,
        trainer,
        name="Sentadilla",
        equipment_needed="Barra olímpica",
        has_no_materials_alternative=True,
    )
    pushup_id = create_exercise(
        api,
        trainer,
        name="Flexiones de brazos",
        equipment_needed="Colchoneta",
        has_no_materials_alternative=True,
    )
    template = create_template(
        api,
        trainer,
        squat_id,
        pushup_id,
        name="Plan Adaptable",
        has_no_materials_alternative=True,
    )
    rel_id = link_student(sessions, "coach@us55.com", "student@us55.com")
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": template["id"]},
    )

    # 1. Inicialmente la rutina asignada se encuentra en modalidad GYM
    initial_resp = api.get(ASSIGNED_PATH, headers=student)
    assert initial_resp.status_code == 200
    initial_data = initial_resp.json()
    assert initial_data["modality"] == "GYM"
    assert len(initial_data["days"][0]["blocks"][0]["exercises"]) == 2

    # 2. Alternar a Casa/Viaje (HOME)
    home_resp = api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"})
    assert home_resp.status_code == 200
    home_data = home_resp.json()
    assert home_data["modality"] == "HOME"
    assert [
        ex["exercise"]["has_no_materials_alternative"]
        for ex in home_data["days"][0]["blocks"][0]["exercises"]
    ] == [True, True]

    # Verificar que GET /assigned persiste la modalidad HOME
    get_home = api.get(ASSIGNED_PATH, headers=student)
    assert get_home.status_code == 200
    assert get_home.json()["modality"] == "HOME"

    # 3. Volver a Gimnasio (GYM)
    gym_resp = api.put(MODALITY_PATH, headers=student, json={"modality": "GYM"})
    assert gym_resp.status_code == 200
    assert gym_resp.json()["modality"] == "GYM"
    assert api.get(ASSIGNED_PATH, headers=student).json()["modality"] == "GYM"


def test_us55_ca2_blocks_switch_to_home_and_informs_exercises_without_alternative(client):
    """CA-2: Si un ejercicio no tiene alternativa 'Sin materiales', bloquea el cambio e informa cuáles son y por qué."""
    api, sessions = client
    trainer = register_and_login(api, "coach2@us55.com", "TRAINER")
    student = register_and_login(api, "student2@us55.com", "STUDENT")

    plank_id = create_exercise(
        api,
        trainer,
        name="Plancha abdominal",
        equipment_needed="Peso corporal",
        has_no_materials_alternative=True,
    )
    leg_press_id = create_exercise(
        api,
        trainer,
        name="Prensa 45 grados",
        equipment_needed="Máquina prensa",
        has_no_materials_alternative=False,
    )
    lat_pulldown_id = create_exercise(
        api,
        trainer,
        name="Jalón al pecho en polea",
        equipment_needed="Polea alta",
        has_no_materials_alternative=False,
    )

    template = create_template(
        api,
        trainer,
        days=[
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Fuerza Inferior",
                        "exercises": [entry(plank_id), entry(leg_press_id)],
                    }
                ],
            },
            {
                "name": "Día 2",
                "blocks": [
                    {
                        "name": "Fuerza Superior",
                        "exercises": [entry(lat_pulldown_id)],
                    }
                ],
            },
        ],
    )
    rel_id = link_student(sessions, "coach2@us55.com", "student2@us55.com")
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": template["id"]},
    )

    # Intentar cambiar a HOME debe fallar con 422 Problem Details
    blocked = api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"})
    assert blocked.status_code == 422
    assert blocked.headers["content-type"].startswith("application/problem+json")
    body = blocked.json()
    assert "Prensa 45 grados" in body["detail"]
    assert "Jalón al pecho en polea" in body["detail"]
    assert "Sin materiales" in body["detail"]
    assert len(body["errors"]) == 2
    assert body["errors"][0]["field"] == "days.0.blocks.0.exercises.1.exercise_id"
    assert "Prensa 45 grados" in body["errors"][0]["message"]
    assert "Máquina prensa" in body["errors"][0]["message"]
    assert body["errors"][1]["field"] == "days.1.blocks.0.exercises.0.exercise_id"
    assert "Jalón al pecho en polea" in body["errors"][1]["message"]

    # La modalidad activa debe permanecer en GYM
    assert api.get(ASSIGNED_PATH, headers=student).json()["modality"] == "GYM"


def test_us55_ca3_consolidated_history_across_gym_and_home_modalities(client):
    """CA-3: Los registros de series y cargas en ambas modalidades se consolidan en el mismo historial general."""
    api, sessions = client
    trainer = register_and_login(api, "coach3@us55.com", "TRAINER")
    student = register_and_login(api, "student3@us55.com", "STUDENT")

    squat_id = create_exercise(
        api,
        trainer,
        name="Sentadilla Goblet",
        equipment_needed="Mancuerna",
        has_no_materials_alternative=True,
    )
    template = create_template(
        api,
        trainer,
        squat_id,
        name="Rutina Consolidada",
        has_no_materials_alternative=True,
    )
    rel_id = link_student(sessions, "coach3@us55.com", "student3@us55.com")
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": template["id"]},
    )

    # 1. Registrar serie en modalidad GYM
    log_gym_1 = api.post(
        WORKOUT_LOGS_PATH,
        headers=student,
        json={
            "exercise_id": squat_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 24.0,
        },
    )
    assert log_gym_1.status_code == 201, log_gym_1.text
    assert log_gym_1.json()["modality"] == "GYM"
    assert log_gym_1.json()["weight_kg"] == 24.0

    # 2. Alternar a modalidad HOME
    switch_home = api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"})
    assert switch_home.status_code == 200
    assert switch_home.json()["modality"] == "HOME"

    # Verificar que el registro previo en GYM no se perdió ni se duplicó al cambiar a HOME
    logs_after_switch = api.get(WORKOUT_LOGS_PATH, headers=student).json()
    assert len(logs_after_switch) == 1
    assert logs_after_switch[0]["id"] == log_gym_1.json()["id"]

    # 3. Registrar serie en modalidad HOME (peso corporal / 0 kg)
    log_home_2 = api.post(
        WORKOUT_LOGS_PATH,
        headers=student,
        json={
            "exercise_id": squat_id,
            "day_name": "Día 1",
            "set_number": 2,
            "reps_completed": "15",
            "weight_kg": 0.0,
        },
    )
    assert log_home_2.status_code == 201, log_home_2.text
    assert log_home_2.json()["modality"] == "HOME"
    assert log_home_2.json()["weight_kg"] == 0.0

    # 4. Volver a modalidad GYM y registrar una tercera serie
    switch_gym = api.put(MODALITY_PATH, headers=student, json={"modality": "GYM"})
    assert switch_gym.status_code == 200

    log_gym_3 = api.post(
        WORKOUT_LOGS_PATH,
        headers=student,
        json={
            "exercise_id": squat_id,
            "day_name": "Día 1",
            "set_number": 3,
            "reps_completed": "10",
            "weight_kg": 26.0,
        },
    )
    assert log_gym_3.status_code == 201

    # 5. Consultar el historial general: debe consolidar los 3 registros sin fragmentación
    history_resp = api.get(WORKOUT_LOGS_PATH, headers=student)
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 3
    assert {item["id"] for item in history} == {
        log_gym_1.json()["id"],
        log_home_2.json()["id"],
        log_gym_3.json()["id"],
    }
    assert [item["modality"] for item in sorted(history, key=lambda x: x["set_number"])] == [
        "GYM",
        "HOME",
        "GYM",
    ]

    # Filtrado opcional por exercise_id sigue devolviendo el historial consolidado de ese ejercicio
    filtered = api.get(f"{WORKOUT_LOGS_PATH}?exercise_id={squat_id}", headers=student)
    assert filtered.status_code == 200
    assert len(filtered.json()) == 3


def test_us55_materialized_student_routine_and_trainer_draft_resets_home_if_incompatible(client):
    """Verifica alternancia sobre copia propia (StudentRoutine) y reseteo a GYM si el entrenador agrega un ejercicio sin alternativa."""
    api, sessions = client
    trainer = register_and_login(api, "coach4@us55.com", "TRAINER")
    student = register_and_login(api, "student4@us55.com", "STUDENT")

    lunge_id = create_exercise(
        api,
        trainer,
        name="Estocadas",
        equipment_needed="Mancuernas",
        has_no_materials_alternative=True,
    )
    cable_row_id = create_exercise(
        api,
        trainer,
        name="Remo en polea baja",
        equipment_needed="Polea baja",
        has_no_materials_alternative=False,
    )
    template = create_template(
        api,
        trainer,
        lunge_id,
        name="Base Adaptable",
        has_no_materials_alternative=True,
    )
    rel_id = link_student(sessions, "coach4@us55.com", "student4@us55.com")
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": template["id"]},
    )

    with sessions() as db:
        student_id = db.scalar(select(StudentProfile.id))

    # Materializar StudentRoutine abriendo el editor del entrenador
    opened = api.get(f"/api/v1/trainers/me/students/{student_id}/routine", headers=trainer)
    assert opened.status_code == 200

    # El alumno alterna su StudentRoutine a HOME
    switched = api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"})
    assert switched.status_code == 200
    assert switched.json()["modality"] == "HOME"

    # El entrenador edita la rutina del alumno agregando un ejercicio sin alternativa y desmarcando el flag
    draft_payload = {
        "draft_version": opened.json()["draft_version"],
        "name": "Base Editada con Máquina",
        "duration_weeks": 4,
        "intensity": "MEDIA",
        "has_no_materials_alternative": False,
        "desired_weekly_volume": None,
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Principal",
                        "estimated_duration_minutes": 25,
                        "exercises": [entry(lunge_id), entry(cable_row_id)],
                    }
                ],
            }
        ],
    }
    saved = api.put(
        f"/api/v1/trainers/me/students/{student_id}/routine/draft",
        headers=trainer,
        json=draft_payload,
    )
    assert saved.status_code == 200
    confirmed = api.post(
        f"/api/v1/trainers/me/students/{student_id}/routine/draft/confirm",
        headers=trainer,
    )
    assert confirmed.status_code == 200

    # Al no ser compatible con HOME, la modalidad del alumno vuelve automáticamente a GYM
    current_view = api.get(ASSIGNED_PATH, headers=student).json()
    assert current_view["modality"] == "GYM"

    # Y si el alumno intenta volver a HOME con el ejercicio nuevo, es bloqueado con mensaje claro
    blocked = api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"})
    assert blocked.status_code == 422
    assert "Remo en polea baja" in blocked.json()["detail"]


def test_us55_edge_cases_and_validations(client):
    """Valida errores 404 sin rutina asignada, validación de esquemas, reasignación e integración con AssignedRoutine."""
    api, sessions = client
    trainer = register_and_login(api, "coach5@us55.com", "TRAINER")
    student = register_and_login(api, "student5@us55.com", "STUDENT")
    rel_id = link_student(sessions, "coach5@us55.com", "student5@us55.com")

    # Sin rutina asignada -> 404 al cambiar modalidad o registrar serie
    assert api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"}).status_code == 404
    assert (
        api.post(
            WORKOUT_LOGS_PATH,
            headers=student,
            json={
                "exercise_id": "non-existent",
                "day_name": "Día 1",
                "set_number": 1,
                "reps_completed": "10",
            },
        ).status_code
        == 404
    )

    # Modalidad inválida -> 422
    invalid_mod = api.put(MODALITY_PATH, headers=student, json={"modality": "OUTDOOR"})
    assert invalid_mod.status_code == 422
    empty_mod = api.put(MODALITY_PATH, headers=student, json={"modality": "  "})
    assert empty_mod.status_code == 422

    # Asignar rutina con 1 ejercicio sin alternativa
    machine_ex = create_exercise(
        api,
        trainer,
        name="Camilla de isquios",
        equipment_needed="Camilla",
        has_no_materials_alternative=False,
    )
    foreign_ex = create_exercise(
        api,
        trainer,
        name="Ejercicio ajeno a la rutina",
        equipment_needed="Barra",
        has_no_materials_alternative=True,
    )
    template_machine = create_template(api, trainer, machine_ex, name="Rutina Máquina")
    template_home = create_template(
        api,
        trainer,
        foreign_ex,
        name="Rutina Casa",
        has_no_materials_alternative=True,
    )

    # Primero asignar rutina compatible con HOME y pasar a HOME
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": template_home["id"]},
    )
    assert api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"}).status_code == 200
    assert api.get(ASSIGNED_PATH, headers=student).json()["modality"] == "HOME"

    # Cuando el entrenador reasigna una rutina que no soporta HOME, la modalidad vuelve a GYM
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": template_machine["id"]},
    )
    assert api.get(ASSIGNED_PATH, headers=student).json()["modality"] == "GYM"

    # Bloqueo con 1 único ejercicio (mensaje singular)
    single_block = api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"})
    assert single_block.status_code == 422
    assert 'porque el ejercicio "Camilla de isquios"' in single_block.json()["detail"]

    # Intentar registrar un ejercicio que no pertenece a la rutina activa -> 422
    wrong_ex = api.post(
        WORKOUT_LOGS_PATH,
        headers=student,
        json={
            "exercise_id": foreign_ex,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
        },
    )
    assert wrong_ex.status_code == 422

    # Intentar forzar modality="HOME" en el log de un ejercicio sin alternativa -> 422
    forced_home = api.post(
        WORKOUT_LOGS_PATH,
        headers=student,
        json={
            "exercise_id": machine_ex,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "modality": "HOME",
        },
    )
    assert forced_home.status_code == 422
    assert "Camilla de isquios" in forced_home.json()["detail"]

    # Probar con AssignedRoutine aprobada vinculada directamente a initial_routine_id sin StudentRoutine previa
    now = datetime.now(UTC)
    with sessions() as db:
        rel_obj = db.get(TrainingRelationship, rel_id)
        ar = AssignedRoutine(
            trainer_id=rel_obj.trainer_id,
            student_id=rel_obj.student_id,
            name="Rutina IA Aprobada",
            duration_weeks=4,
            intensity="MEDIA",
            has_no_materials_alternative=True,
            status="APPROVED",
            approved_at=now,
            created_at=now,
            updated_at=now,
            days=[
                AssignedRoutineDay(
                    order_index=0,
                    name="Día IA",
                    blocks=[
                        AssignedRoutineBlock(
                            order_index=0,
                            name="Principal",
                            exercises=[
                                AssignedRoutineExercise(
                                    order_index=0,
                                    exercise_id=foreign_ex,
                                    sets=3,
                                    reps="12",
                                    rest_seconds=45,
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        db.add(ar)
        db.flush()
        rel_obj.initial_routine_id = ar.id
        db.commit()

    ai_home = api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"})
    assert ai_home.status_code == 200
    assert ai_home.json()["modality"] == "HOME"


def test_us55_security_ownership_and_auto_reset_on_exercise_edit(client):
    """Verifica RBAC (403 para entrenadores), pérdida de acceso al terminar vínculo y auto-reseteo a GYM."""
    api, sessions = client
    trainer = register_and_login(api, "coach6@us55.com", "TRAINER")
    student = register_and_login(api, "student6@us55.com", "STUDENT")
    rel_id = link_student(sessions, "coach6@us55.com", "student6@us55.com")

    # Un entrenador no puede invocar endpoints exclusivos del alumno (403 Forbidden)
    assert api.put(MODALITY_PATH, headers=trainer, json={"modality": "HOME"}).status_code == 403
    assert api.get(WORKOUT_LOGS_PATH, headers=trainer).status_code == 403
    assert (
        api.post(
            WORKOUT_LOGS_PATH,
            headers=trainer,
            json={
                "exercise_id": "any",
                "day_name": "Día 1",
                "set_number": 1,
                "reps_completed": "10",
            },
        ).status_code
        == 403
    )

    # Plantilla con has_no_materials_alternative=False pero ejercicio con alternativa=True
    ex_id = create_exercise(
        api,
        trainer,
        name="Press con mancuernas",
        equipment_needed="Mancuernas",
        has_no_materials_alternative=True,
    )
    tpl = create_template(
        api,
        trainer,
        ex_id,
        name="Plantilla Sin Marca Global",
        has_no_materials_alternative=False,
    )
    api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_id}",
        headers=trainer,
        json={"routine_template_id": tpl["id"]},
    )

    # El alumno puede cambiar a HOME porque el ejercicio sí tiene alternativa
    assert api.put(MODALITY_PATH, headers=student, json={"modality": "HOME"}).status_code == 200
    assert api.get(ASSIGNED_PATH, headers=student).json()["modality"] == "HOME"

    # El entrenador quita la alternativa 'Sin materiales' del ejercicio en su biblioteca
    edited_ex = api.put(
        f"{EXERCISES_PATH}/{ex_id}",
        headers=trainer,
        json={
            "name": "Press con mancuernas",
            "description": "Descripción técnica de Press con mancuernas",
            "category": "FUERZA",
            "target_muscle_group": "Cuádriceps",
            "equipment_needed": "Mancuernas",
            "has_no_materials_alternative": False,
        },
    )
    assert edited_ex.status_code == 200

    # Al consultar la rutina asignada, el sistema detecta que ya no soporta HOME y restablece GYM
    assert api.get(ASSIGNED_PATH, headers=student).json()["modality"] == "GYM"

    # Si el vínculo pasa a TERMINATED, el alumno pierde acceso a la rutina y al historial (Principio III)
    with sessions() as db:
        db.get(TrainingRelationship, rel_id).status = "TERMINATED"
        db.commit()

    assert api.put(MODALITY_PATH, headers=student, json={"modality": "GYM"}).status_code == 404
    assert api.get(WORKOUT_LOGS_PATH, headers=student).json() == []
