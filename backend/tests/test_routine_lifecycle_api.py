"""Spec 012: eliminar rutinas y conservar las generadas con IA."""

import pytest
from sqlalchemy import select

from backend.src.models.assigned_routine import AssignedRoutine
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_routine import StudentRoutine
from backend.src.models.training_relationship import TrainingRelationship
from backend.tests.test_ai_routine_api import (
    create_exercise,
    create_template,
    register_and_login,
    setup_trainer_and_student_relationship,
)

TEMPLATES_PATH = "/api/v1/routine-templates"
AI_PATH = "/api/v1/routines/assigned"
ASSIGNED_VIEW_PATH = "/api/v1/students/me/routine-templates/assigned"
TRAINER = "trainer@test.com"
STUDENT = "student@test.com"


@pytest.fixture(autouse=True)
def _heuristic_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "heuristic")
    monkeypatch.delenv("AI_ROUTINE_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture
def scenario(client):
    api, sessions = client
    trainer = register_and_login(api, TRAINER, "TRAINER")
    student = register_and_login(api, STUDENT, "STUDENT")
    _, student_id = setup_trainer_and_student_relationship(sessions, TRAINER, STUDENT)
    template = create_template(api, trainer, [create_exercise(api, trainer)])
    with sessions() as db:
        relationship_id = db.scalar(select(TrainingRelationship.id))
    return api, sessions, trainer, student, student_id, template, relationship_id


def assign(api, headers, relationship_id: str, routine_id: str | None):
    return api.put(
        f"{TEMPLATES_PATH}/assignments/{relationship_id}", headers=headers, json={"routine_template_id": routine_id}
    )


def generate(api, headers, student_id: str, template_id: str) -> dict:
    response = api.post(
        "/api/v1/routines/generate-ai", headers=headers, json={"student_id": student_id, "template_id": template_id}
    )
    assert response.status_code == 201
    return response.json()


def approve(api, headers, routine_id: str) -> None:
    assert api.post(f"{AI_PATH}/{routine_id}/approve", headers=headers).status_code == 200


def test_delete_unassigned_template(scenario):
    api, _, trainer, _, _, template, _ = scenario

    assert api.delete(f"{TEMPLATES_PATH}/{template['id']}", headers=trainer).status_code == 204

    assert api.get(TEMPLATES_PATH, headers=trainer).json() == []


def test_delete_assigned_template_keeps_student_copy_even_if_never_opened(scenario):
    api, sessions, trainer, student, student_id, template, relationship_id = scenario
    assert assign(api, trainer, relationship_id, template["id"]).status_code == 200

    assert api.delete(f"{TEMPLATES_PATH}/{template['id']}", headers=trainer).status_code == 204

    assert api.get(ASSIGNED_VIEW_PATH, headers=student).json()["name"] == template["name"]
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/routine", headers=trainer).status_code == 200
    with sessions() as db:
        assert db.get(TrainingRelationship, relationship_id).initial_routine_id is None
        assert db.scalar(select(StudentRoutine.status)) == "ACTIVE"
    assignments = api.get(f"{TEMPLATES_PATH}/assignments", headers=trainer).json()
    assert assignments[0]["routine_name"] == template["name"]


def test_delete_template_keeps_ai_routines_based_on_it(scenario):
    api, sessions, trainer, _, student_id, template, _ = scenario
    routine = generate(api, trainer, student_id, template["id"])

    assert api.delete(f"{TEMPLATES_PATH}/{template['id']}", headers=trainer).status_code == 204

    with sessions() as db:
        assert db.get(AssignedRoutine, routine["id"]).template_id is None


def test_cannot_delete_foreign_routines(scenario):
    api, sessions, trainer, student, student_id, template, _ = scenario
    routine = generate(api, trainer, student_id, template["id"])
    other = register_and_login(api, "other@test.com", "TRAINER")

    assert api.delete(f"{TEMPLATES_PATH}/{template['id']}", headers=other).status_code == 404
    assert api.delete(f"{AI_PATH}/{routine['id']}", headers=other).status_code == 404
    assert api.delete(f"{AI_PATH}/{routine['id']}", headers=student).status_code == 403
    with sessions() as db:
        assert db.get(RoutineTemplate, template["id"]) is not None
        assert db.get(AssignedRoutine, routine["id"]) is not None


def test_delete_approved_ai_routine_keeps_student_copy(scenario):
    api, sessions, trainer, student, student_id, template, relationship_id = scenario
    routine = generate(api, trainer, student_id, template["id"])
    approve(api, trainer, routine["id"])

    assert api.delete(f"{AI_PATH}/{routine['id']}", headers=trainer).status_code == 204

    assert api.get(ASSIGNED_VIEW_PATH, headers=student).json()["name"] == routine["name"]
    assert api.get(AI_PATH, headers=trainer).json() == []
    with sessions() as db:
        assert db.get(TrainingRelationship, relationship_id).initial_routine_id is None


def test_trainer_lists_saved_ai_routines_with_student_and_state(scenario):
    api, _, trainer, _, student_id, template, relationship_id = scenario
    first = generate(api, trainer, student_id, template["id"])
    second = generate(api, trainer, student_id, template["id"])
    approve(api, trainer, second["id"])

    saved = {item["id"]: item for item in api.get(AI_PATH, headers=trainer).json()}

    assert set(saved) == {first["id"], second["id"]}
    assert saved[first["id"]]["status"] == "PENDING_REVIEW"
    assert saved[first["id"]]["is_assigned"] is False
    assert saved[second["id"]]["is_assigned"] is True
    assert saved[second["id"]]["student_name"] == "Valeria Alumna"
    assert saved[second["id"]]["relationship_id"] == relationship_id
    assert saved[second["id"]]["adaptation_summary"]
    assert saved[second["id"]]["days"]


def test_list_is_private_per_trainer_and_requires_active_relationship(scenario):
    api, sessions, trainer, student, student_id, template, relationship_id = scenario
    generate(api, trainer, student_id, template["id"])
    other = register_and_login(api, "other@test.com", "TRAINER")

    assert api.get(AI_PATH, headers=other).json() == []
    assert api.get(AI_PATH, headers=student).status_code == 403

    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()
    assert api.get(AI_PATH, headers=trainer).json() == []


def test_approved_ai_routine_can_be_reassigned_without_regenerating(scenario):
    api, _, trainer, student, student_id, template, relationship_id = scenario
    routine = generate(api, trainer, student_id, template["id"])
    approve(api, trainer, routine["id"])
    assert assign(api, trainer, relationship_id, template["id"]).status_code == 200
    assert api.get(ASSIGNED_VIEW_PATH, headers=student).json()["name"] == template["name"]

    response = assign(api, trainer, relationship_id, routine["id"])

    assert response.status_code == 200
    assert api.get(ASSIGNED_VIEW_PATH, headers=student).json()["name"] == routine["name"]
    assert api.get(AI_PATH, headers=trainer).json()[0]["is_assigned"] is True
    assert api.get(f"{TEMPLATES_PATH}/assignments", headers=trainer).json()[0]["routine_name"] == routine["name"]


def test_pending_ai_routine_cannot_be_assigned(scenario):
    api, _, trainer, student, student_id, template, relationship_id = scenario
    routine = generate(api, trainer, student_id, template["id"])

    assert assign(api, trainer, relationship_id, routine["id"]).status_code == 404

    assert api.get(ASSIGNED_VIEW_PATH, headers=student).json() is None


def test_ai_routine_cannot_be_assigned_to_another_student(client):
    api, sessions = client
    trainer = register_and_login(api, TRAINER, "TRAINER")
    register_and_login(api, STUDENT, "STUDENT")
    register_and_login(api, "second@test.com", "STUDENT")
    _, student_id = setup_trainer_and_student_relationship(sessions, TRAINER, STUDENT)
    _, second_id = setup_trainer_and_student_relationship(sessions, TRAINER, "second@test.com")
    template = create_template(api, trainer, [create_exercise(api, trainer)])
    routine = generate(api, trainer, student_id, template["id"])
    approve(api, trainer, routine["id"])
    with sessions() as db:
        second_relationship = db.scalar(
            select(TrainingRelationship.id).where(TrainingRelationship.student_id == second_id)
        )

    assert assign(api, trainer, second_relationship, routine["id"]).status_code == 404
