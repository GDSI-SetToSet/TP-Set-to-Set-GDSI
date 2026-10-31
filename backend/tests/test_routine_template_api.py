from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User

TEMPLATES_PATH = "/api/v1/routine-templates"
STUDENT_TEMPLATES_PATH = "/api/v1/students/me/routine-templates"
EXERCISES_PATH = "/api/v1/exercises"
REQUIRED_MESSAGE = "Este campo es obligatorio"


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def exercise_payload(**overrides) -> dict:
    return {
        "name": "Plancha",
        "description": "Isométrico de core",
        "category": "FUERZA",
        "target_muscle_group": "Abdominales",
        "equipment_needed": "Ninguno",
        **overrides,
    }


def create_exercise(api, headers, **overrides) -> str:
    response = api.post(EXERCISES_PATH, headers=headers, json=exercise_payload(**overrides))
    assert response.status_code == 201
    return response.json()["id"]


def entry(exercise_id: str, **overrides) -> dict:
    return {"exercise_id": exercise_id, "sets": 4, "reps": "8-10", "rest_seconds": 60, **overrides}


def template_payload(*exercise_ids: str, **overrides) -> dict:
    return {
        "name": "Fuerza 3 Días",
        "duration_weeks": 4,
        "intensity": "MEDIA",
        "days": [
            {"name": "Día 1", "blocks": [{"name": "Principal", "exercises": [entry(item) for item in exercise_ids]}]}
        ],
        **overrides,
    }


def create_template(api, headers, *exercise_ids: str, **overrides) -> dict:
    response = api.post(TEMPLATES_PATH, headers=headers, json=template_payload(*exercise_ids, **overrides))
    assert response.status_code == 201
    return response.json()


def link_student(sessions, trainer_email: str, student_email: str, status: str = "ACTIVE") -> str:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))
        profile = StudentProfile(user_id=student_user.id, status="PUBLISHED", created_at=now, updated_at=now)
        plan = TrainingPlan(
            trainer_id=trainer_user.trainer_profile.id,
            title="Plan Base",
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
            status=status,
            start_date=now.date(),
        )
        db.add(relationship)
        db.flush()
        relationship_id = relationship.id
        db.commit()
        return relationship_id


def test_create_template_preserves_structure_and_reports_exercises(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    plank = create_exercise(api, trainer)
    run = create_exercise(api, trainer, name="Trote", category="CARDIO", target_muscle_group="Piernas")

    template = create_template(
        api,
        trainer,
        days=[
            {
                "name": "Día 1",
                "blocks": [
                    {"name": "Entrada en calor", "exercises": [entry(run, sets=1, reps="10 min", rest_seconds=0)]},
                    {"name": "Principal", "exercises": [entry(plank), entry(run)]},
                ],
            },
            {"name": "Día 2", "blocks": [{"name": "Principal", "exercises": [entry(plank)]}]},
        ],
    )

    assert template["exercise_count"] == 4
    assert template["has_no_materials_alternative"] is False
    assert [day["name"] for day in template["days"]] == ["Día 1", "Día 2"]
    blocks = template["days"][0]["blocks"]
    assert [block["name"] for block in blocks] == ["Entrada en calor", "Principal"]
    assert [item["exercise"]["category"] for item in blocks[1]["exercises"]] == ["FUERZA", "CARDIO"]
    assert blocks[0]["exercises"][0]["rest_seconds"] == 0
    assert api.get(f"{TEMPLATES_PATH}/{template['id']}", headers=trainer).json() == template
    assert [item["id"] for item in api.get(TEMPLATES_PATH, headers=trainer).json()] == [template["id"]]


def test_create_template_requires_every_parameter(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    plank = create_exercise(api, trainer)

    response = api.post(TEMPLATES_PATH, headers=trainer, json={})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert {item["field"]: item["message"] for item in response.json()["errors"]} == {
        "name": REQUIRED_MESSAGE,
        "duration_weeks": REQUIRED_MESSAGE,
        "intensity": REQUIRED_MESSAGE,
        "days": REQUIRED_MESSAGE,
    }

    missing_entry = template_payload(plank)
    del missing_entry["days"][0]["blocks"][0]["exercises"][0]["sets"]
    response = api.post(TEMPLATES_PATH, headers=trainer, json=missing_entry)
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "days.0.blocks.0.exercises.0.sets", "message": REQUIRED_MESSAGE}]

    assert api.get(TEMPLATES_PATH, headers=trainer).json() == []


def test_create_template_enforces_limits(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    plank = create_exercise(api, trainer)
    day = template_payload(plank)["days"][0]

    invalid_payloads = {
        "name": template_payload(plank, name="x" * 151),
        "duration_weeks": template_payload(plank, duration_weeks=53),
        "intensity": template_payload(plank, intensity="SUAVE"),
        "days": template_payload(plank, days=[]),
    }
    for field, payload in invalid_payloads.items():
        response = api.post(TEMPLATES_PATH, headers=trainer, json=payload)
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == field

    assert api.post(TEMPLATES_PATH, headers=trainer, json=template_payload(plank, days=[day] * 8)).status_code == 422
    no_blocks = template_payload(plank, days=[{"name": "Día 1", "blocks": []}])
    assert api.post(TEMPLATES_PATH, headers=trainer, json=no_blocks).status_code == 422
    no_entries = template_payload(plank, days=[{"name": "Día 1", "blocks": [{"name": "A", "exercises": []}]}])
    assert api.post(TEMPLATES_PATH, headers=trainer, json=no_entries).status_code == 422
    for overrides, field in (({"sets": 21}, "sets"), ({"rest_seconds": 601}, "rest_seconds"), ({"reps": "x" * 51}, "reps")):
        payload = template_payload(plank)
        payload["days"][0]["blocks"][0]["exercises"][0].update(overrides)
        response = api.post(TEMPLATES_PATH, headers=trainer, json=payload)
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == f"days.0.blocks.0.exercises.0.{field}"


def test_template_rejects_unavailable_exercises(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    other = register_and_login(api, "other@example.com", "TRAINER")
    foreign = create_exercise(api, other)
    deleted = create_exercise(api, trainer, name="Dado de baja")
    api.delete(f"{EXERCISES_PATH}/{deleted}", headers=trainer)

    for exercise_id in (foreign, deleted, "no-existe"):
        response = api.post(TEMPLATES_PATH, headers=trainer, json=template_payload(exercise_id))
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "days.0.blocks.0.exercises.0.exercise_id"


def test_update_template_replaces_structure_and_keeps_deleted_exercise(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    plank = create_exercise(api, trainer)
    run = create_exercise(api, trainer, name="Trote")
    template = create_template(api, trainer, plank)
    path = f"{TEMPLATES_PATH}/{template['id']}"
    api.delete(f"{EXERCISES_PATH}/{plank}", headers=trainer)

    assert api.get(path, headers=trainer).json()["days"][0]["blocks"][0]["exercises"][0]["exercise"]["id"] == plank

    updated = api.put(path, headers=trainer, json=template_payload(plank, run, name="Nueva", intensity="EXIGENTE"))
    assert updated.status_code == 200
    body = updated.json()
    assert (body["name"], body["intensity"], body["exercise_count"]) == ("Nueva", "EXIGENTE", 2)
    assert [item["exercise"]["id"] for item in body["days"][0]["blocks"][0]["exercises"]] == [plank, run]

    without_deleted = api.put(path, headers=trainer, json=template_payload(run))
    assert without_deleted.status_code == 200
    readded = api.put(path, headers=trainer, json=template_payload(plank))
    assert readded.status_code == 422
    assert api.get(path, headers=trainer).json()["exercise_count"] == 1


def test_no_materials_template_requires_flag_on_every_exercise(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    flagged = create_exercise(api, trainer, has_no_materials_alternative=True)
    unflagged = create_exercise(api, trainer, name="Press plano")

    rejected = api.post(
        TEMPLATES_PATH,
        headers=trainer,
        json=template_payload(flagged, unflagged, has_no_materials_alternative=True),
    )
    assert rejected.status_code == 422
    errors = rejected.json()["errors"]
    assert [item["field"] for item in errors] == ["days.0.blocks.0.exercises.1.exercise_id"]
    assert "Press plano" in errors[0]["message"]
    assert api.get(TEMPLATES_PATH, headers=trainer).json() == []

    template = create_template(api, trainer, flagged, has_no_materials_alternative=True)
    updated = api.put(
        f"{TEMPLATES_PATH}/{template['id']}",
        headers=trainer,
        json=template_payload(unflagged, has_no_materials_alternative=True),
    )
    assert updated.status_code == 422


def test_exercise_cannot_lose_flag_while_in_no_materials_template(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    flagged = create_exercise(api, trainer, has_no_materials_alternative=True)
    free = create_exercise(api, trainer, name="Libre", has_no_materials_alternative=True)
    template = create_template(api, trainer, flagged, has_no_materials_alternative=True)
    create_template(api, trainer, free)

    conflict = api.put(f"{EXERCISES_PATH}/{flagged}", headers=trainer, json=exercise_payload())
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")
    assert api.get(f"{EXERCISES_PATH}/{flagged}", headers=trainer).json()["has_no_materials_alternative"] is True

    renamed = exercise_payload(name="Plancha alta", has_no_materials_alternative=True)
    assert api.put(f"{EXERCISES_PATH}/{flagged}", headers=trainer, json=renamed).status_code == 200
    # Una rutina sin la marca no bloquea el cambio.
    assert api.put(f"{EXERCISES_PATH}/{free}", headers=trainer, json=exercise_payload()).status_code == 200

    released = api.put(f"{TEMPLATES_PATH}/{template['id']}", headers=trainer, json=template_payload(flagged))
    assert released.status_code == 200
    assert api.put(f"{EXERCISES_PATH}/{flagged}", headers=trainer, json=exercise_payload()).status_code == 200


def test_templates_are_isolated_between_trainers_and_roles(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    other = register_and_login(api, "other@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    plank = create_exercise(api, trainer)
    other_plank = create_exercise(api, other)
    path = f"{TEMPLATES_PATH}/{create_template(api, trainer, plank)['id']}"

    assert api.get(TEMPLATES_PATH, headers=other).json() == []
    assert api.get(path, headers=other).status_code == 404
    assert api.put(path, headers=other, json=template_payload(other_plank)).status_code == 404
    assert api.get(TEMPLATES_PATH, headers=student).status_code == 403
    assert api.post(TEMPLATES_PATH, headers=student, json=template_payload(plank)).status_code == 403
    assert api.get(TEMPLATES_PATH).status_code == 401
    assert api.get(STUDENT_TEMPLATES_PATH, headers=trainer).status_code == 403


def test_student_with_active_relationship_reads_templates(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    api.put(
        "/api/v1/trainers/me/profile",
        headers=trainer,
        json={"full_name": "Lucas Pérez", "contact_phone": "+5491155551234", "specialty": "Fuerza"},
    )
    template = create_template(api, trainer, create_exercise(api, trainer))
    link_student(sessions, "coach@example.com", "student@example.com")

    listed = api.get(STUDENT_TEMPLATES_PATH, headers=student)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [template["id"]]
    assert listed.json()[0]["trainer_name"] == "Lucas Pérez"

    detail = api.get(f"{STUDENT_TEMPLATES_PATH}/{template['id']}", headers=student)
    assert detail.status_code == 200
    assert detail.json()["exercise_count"] == 1
    assert api.put(f"{TEMPLATES_PATH}/{template['id']}", headers=student, json={}).status_code == 422


def test_student_without_active_relationship_cannot_read_templates(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    stranger = register_and_login(api, "stranger@example.com", "STUDENT")
    former = register_and_login(api, "former@example.com", "STUDENT")
    template = create_template(api, trainer, create_exercise(api, trainer))
    link_student(sessions, "coach@example.com", "former@example.com", status="TERMINATED")

    for student in (stranger, former):
        assert api.get(STUDENT_TEMPLATES_PATH, headers=student).json() == []
        assert api.get(f"{STUDENT_TEMPLATES_PATH}/{template['id']}", headers=student).status_code == 404


def test_trainer_assigns_and_removes_routine_for_active_students(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    another_trainer = register_and_login(api, "other-coach@example.com", "TRAINER")
    active_student = register_and_login(api, "active-student@example.com", "STUDENT")
    register_and_login(api, "former-student@example.com", "STUDENT")

    own_template = create_template(api, trainer, create_exercise(api, trainer))
    foreign_template = create_template(api, another_trainer, create_exercise(api, another_trainer))
    active_relationship_id = link_student(sessions, "coach@example.com", "active-student@example.com")
    inactive_relationship_id = link_student(
        sessions, "coach@example.com", "former-student@example.com", status="TERMINATED"
    )

    assignments_path = f"{TEMPLATES_PATH}/assignments"
    assignment_path = f"{assignments_path}/{active_relationship_id}"
    listed = api.get(assignments_path, headers=trainer)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["student_name"] == "active-student@example.com"
    assert listed.json()[0]["routine_template_id"] is None

    assigned = api.put(
        assignment_path,
        headers=trainer,
        json={"routine_template_id": own_template["id"]},
    )
    assert assigned.status_code == 200
    assert assigned.json() == {
        "relationship_id": active_relationship_id,
        "routine_template_id": own_template["id"],
    }

    listed = api.get(assignments_path, headers=trainer)
    assert listed.json()[0]["routine_template_id"] == own_template["id"]
    assert listed.json()[0]["routine_name"] == own_template["name"]

    assert (
        api.put(assignment_path, headers=trainer, json={"routine_template_id": foreign_template["id"]}).status_code
        == 404
    )
    assert (
        api.put(assignment_path, headers=another_trainer, json={"routine_template_id": foreign_template["id"]}).status_code
        == 404
    )
    assert (
        api.put(
            f"{assignments_path}/{inactive_relationship_id}",
            headers=trainer,
            json={"routine_template_id": own_template["id"]},
        ).status_code
        == 404
    )

    cleared = api.put(assignment_path, headers=trainer, json={"routine_template_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["routine_template_id"] is None
    assert api.get(assignments_path, headers=trainer).json()[0]["routine_template_id"] is None
    assert api.get(f"{STUDENT_TEMPLATES_PATH}/assigned", headers=active_student).json() is None


def test_assigned_routine_is_visible_with_day_durations_and_prescribed_weights(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    student = register_and_login(api, "student@example.com", "STUDENT")
    plank_id = create_exercise(api, trainer, name="Plancha")
    squat_id = create_exercise(api, trainer, name="Sentadilla")
    relationship_id = link_student(sessions, "coach@example.com", "student@example.com")

    template = create_template(
        api,
        trainer,
        plank_id,
        squat_id,
        days=[
            {
                "name": "Día A",
                "blocks": [
                    {
                        "name": "Entrada en calor",
                        "estimated_duration_minutes": 6,
                        "exercises": [entry(plank_id, sets=1, reps="5 min", rest_seconds=0)],
                    },
                    {
                        "name": "Principal",
                        "estimated_duration_minutes": 14,
                        "exercises": [entry(squat_id, sets=3, reps="8", target_weight_kg=25)],
                    },
                ],
            },
            {
                "name": "Día C",
                "blocks": [
                    {
                        "name": "Movilidad",
                        "estimated_duration_minutes": 9,
                        "exercises": [entry(plank_id, sets=2, reps="30 s", rest_seconds=15, target_weight_kg=0)],
                    }
                ],
            },
        ],
    )

    assigned_path = f"{STUDENT_TEMPLATES_PATH}/assigned"
    assert api.get(assigned_path, headers=student).status_code == 200
    assert api.get(assigned_path, headers=student).json() is None

    assignment = api.put(
        f"{TEMPLATES_PATH}/assignments/{relationship_id}",
        headers=trainer,
        json={"routine_template_id": template["id"]},
    )
    assert assignment.status_code == 200

    response = api.get(assigned_path, headers=student)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == template["id"]
    assert data["name"] == "Fuerza 3 Días"
    assert [day["name"] for day in data["days"]] == ["Día A", "Día C"]
    first_day_blocks = data["days"][0]["blocks"]
    assert [block["estimated_duration_minutes"] for block in first_day_blocks] == [6, 14]
    assert first_day_blocks[1]["exercises"][0]["exercise"]["name"] == "Sentadilla"
    assert first_day_blocks[1]["exercises"][0]["target_weight_kg"] == 25
    assert data["days"][1]["blocks"][0]["exercises"][0]["target_weight_kg"] == 0
