from datetime import UTC, datetime

from sqlalchemy import select
from test_routine_template_api import (
    EXERCISES_PATH,
    STUDENT_TEMPLATES_PATH,
    TEMPLATES_PATH,
    create_exercise,
    create_template,
    entry,
    exercise_payload,
    link_student,
    register_and_login,
    template_payload,
)

from backend.src.models import (
    ProtectedZone,
    RoutineChangeLog,
    StudentProfile,
    StudentRoutine,
    TrainingRelationship,
)


def setup_case(client, **template_overrides):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    student = register_and_login(api, "alumno@example.com", "STUDENT")
    squat = create_exercise(api, trainer, name="Sentadilla", target_muscle_group="Piernas")
    plank = create_exercise(api, trainer)
    template = create_template(api, trainer, squat, **template_overrides)
    relationship_id = link_student(sessions, "coach@example.com", "alumno@example.com")
    api.put(
        f"{TEMPLATES_PATH}/assignments/{relationship_id}", headers=trainer, json={"routine_template_id": template["id"]}
    )
    with sessions() as db:
        student_id = db.get(TrainingRelationship, relationship_id).student_id
    return api, sessions, trainer, student, student_id, template, squat, plank


def path(student_id: str, suffix: str = "") -> str:
    return f"/api/v1/trainers/me/students/{student_id}/routine{suffix}"


def draft(version: int, *ids: str, **overrides) -> dict:
    body = template_payload(*ids, **overrides)
    body["draft_version"] = version
    return body


def test_edit_in_draft_keeps_student_view_until_confirmed(client):
    api, sessions, trainer, student, sid, template, squat, plank = setup_case(client)

    current = api.get(path(sid), headers=trainer).json()
    assert current["draft"] is None and current["routine"]["exercise_count"] == 1

    saved = api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, plank, intensity="ALTA"))
    assert saved.status_code == 200 and saved.json()["draft_version"] == 1
    shown = api.get(path(sid), headers=trainer).json()
    assert shown["status"] == "DRAFT_PENDING" and shown["draft"]["exercise_count"] == 2
    assert shown["routine"]["intensity"] == "MEDIA"

    student_view = api.get(f"{STUDENT_TEMPLATES_PATH}/assigned", headers=student).json()
    assert student_view["intensity"] == "MEDIA" and student_view["exercise_count"] == 1

    confirmed = api.post(path(sid, "/draft/confirm"), headers=trainer)
    assert confirmed.status_code == 200
    assert confirmed.json()["routine"]["exercise_count"] == 2 and confirmed.json()["draft"] is None
    student_view = api.get(f"{STUDENT_TEMPLATES_PATH}/assigned", headers=student).json()
    assert student_view["intensity"] == "ALTA" and student_view["exercise_count"] == 2

    # la plantilla compartida no se modifica
    assert api.get(f"{TEMPLATES_PATH}/{template['id']}", headers=trainer).json()["exercise_count"] == 1
    with sessions() as db:
        log = db.scalar(select(RoutineChangeLog))
        assert log.changes["added"] == [plank] and log.changes["fields"]["intensity"]["after"] == "ALTA"
        assert log.confirmed_at is not None and log.trainer_id


def test_stale_draft_version_conflicts_and_discard_restores_active(client):
    api, _, trainer, _, sid, _, squat, plank = setup_case(client)
    assert api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat)).status_code == 200
    assert api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, plank)).status_code == 409
    assert api.delete(path(sid, "/draft"), headers=trainer).status_code == 204
    shown = api.get(path(sid), headers=trainer).json()
    assert shown["draft"] is None and shown["status"] == "ACTIVE"
    assert api.post(path(sid, "/draft/confirm"), headers=trainer).status_code == 409


def test_contraindicated_exercise_is_blocked_and_cannot_be_forced(client):
    api, sessions, trainer, _, sid, _, squat, plank = setup_case(client)
    api.put(
        f"{EXERCISES_PATH}/{plank}",
        headers=trainer,
        json=exercise_payload(contraindicated_zones=["knee"]),
    )
    with sessions() as db:
        db.add(ProtectedZone(student_id=sid, body_area="Knee", created_at=datetime.now(UTC)))
        db.commit()

    blocked = api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, plank))
    assert blocked.status_code == 422
    assert "rodilla" in str(blocked.json())
    assert api.get(path(sid), headers=trainer).json()["draft"] is None


def test_no_materials_blocks_confirm_only_for_added_exercises(client):
    api, _, trainer, _, sid, _, squat, plank = setup_case(client)
    squat_body = exercise_payload(name="Sentadilla", target_muscle_group="Piernas", has_no_materials_alternative=True)
    api.put(f"{EXERCISES_PATH}/{squat}", headers=trainer, json=squat_body)
    # marcar la rutina del alumno como "Sin materiales" en el borrador
    body = draft(0, squat, plank, has_no_materials_alternative=True)
    assert api.put(path(sid, "/draft"), headers=trainer, json=body).status_code == 200  # borrador incompleto OK
    assert api.post(path(sid, "/draft/confirm"), headers=trainer).status_code == 422

    # solo cambiar parámetros de un ejercicio existente no exige nueva alternativa
    api.delete(path(sid, "/draft"), headers=trainer)
    version = api.get(path(sid), headers=trainer).json()["draft_version"]
    only_params = draft(version, squat, has_no_materials_alternative=True)
    only_params["days"][0]["blocks"][0]["exercises"][0]["sets"] = 6
    assert api.put(path(sid, "/draft"), headers=trainer, json=only_params).status_code == 200
    assert api.post(path(sid, "/draft/confirm"), headers=trainer).status_code == 200


def test_weekly_volume_is_validated_and_persisted(client):
    api, _, trainer, _, sid, _, squat, _ = setup_case(client)
    assert api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, desired_weekly_volume=8)).status_code == 422
    assert api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, desired_weekly_volume=3)).status_code == 200
    confirmed = api.post(path(sid, "/draft/confirm"), headers=trainer).json()
    assert confirmed["desired_weekly_volume"] == 3


def test_invalid_values_unknown_and_foreign_exercises_are_rejected(client):
    api, _, trainer, _, sid, _, squat, _ = setup_case(client)
    bad = draft(0, squat)
    bad["days"][0]["blocks"][0]["exercises"][0]["sets"] = 0
    assert api.put(path(sid, "/draft"), headers=trainer, json=bad).status_code == 422
    assert api.put(path(sid, "/draft"), headers=trainer, json=draft(0, "no-existe")).status_code == 422


def test_other_trainer_terminated_link_and_missing_routine_are_forbidden(client):
    api, sessions, trainer, student, sid, _, squat, _ = setup_case(client)
    other = register_and_login(api, "otro@example.com", "TRAINER")
    assert api.get(path(sid), headers=other).status_code == 403
    assert api.put(path(sid, "/draft"), headers=other, json=draft(0, squat)).status_code == 403
    assert api.get(path(sid), headers=student).status_code in (401, 403)

    with sessions() as db:
        db.scalar(select(TrainingRelationship)).status = "TERMINATED"
        db.commit()
    assert api.get(path(sid), headers=trainer).status_code == 403


def test_student_without_assigned_routine_gets_404(client):
    api, sessions = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    create_exercise(api, trainer)
    register_and_login(api, "alumno@example.com", "STUDENT")
    link_student(sessions, "coach@example.com", "alumno@example.com")
    with sessions() as db:
        sid = db.scalar(select(StudentProfile)).id
    assert api.get(path(sid), headers=trainer).status_code == 404


def test_edit_keeps_working_with_deleted_exercise_already_in_routine(client):
    api, _, trainer, _, sid, _, squat, plank = setup_case(client)
    api.get(path(sid), headers=trainer)
    api.delete(f"{EXERCISES_PATH}/{squat}", headers=trainer)
    assert api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat)).status_code == 200
    assert api.put(path(sid, "/draft"), headers=trainer, json=draft(1, plank, squat)).status_code == 200
    with_new_deleted = api.put(path(sid, "/draft"), headers=trainer, json=draft(2, plank))
    assert with_new_deleted.status_code == 200
    assert entry(plank)["exercise_id"] == plank


def test_copy_is_persisted_once_per_relationship(client):
    api, sessions, trainer, _, sid, *_ = setup_case(client)
    api.get(path(sid), headers=trainer)
    api.get(path(sid), headers=trainer)
    with sessions() as db:
        assert len(list(db.scalars(select(StudentRoutine)))) == 1


def test_reassigning_replaces_copy_and_unassigning_hides_it(client):
    api, _, trainer, student, sid, _template, squat, plank = setup_case(client)
    api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, plank))
    api.post(path(sid, "/draft/confirm"), headers=trainer)
    other = create_template(api, trainer, plank, name="Otra")
    relationship_id = api.get(f"{TEMPLATES_PATH}/assignments", headers=trainer).json()[0]["relationship_id"]
    assignment = f"{TEMPLATES_PATH}/assignments/{relationship_id}"

    api.put(assignment, headers=trainer, json={"routine_template_id": other["id"]})
    seen = api.get(f"{STUDENT_TEMPLATES_PATH}/assigned", headers=student).json()
    assert seen["name"] == "Otra" and seen["exercise_count"] == 1

    api.put(assignment, headers=trainer, json={"routine_template_id": None})
    assert api.get(f"{STUDENT_TEMPLATES_PATH}/assigned", headers=student).json() is None
    assert api.get(path(sid), headers=trainer).status_code == 404


def test_exercise_zones_must_come_from_the_body_area_list(client):
    api, _, trainer, _, _, _, squat, _ = setup_case(client)
    body = exercise_payload(name="Sentadilla", target_muscle_group="Piernas")
    bad = api.put(f"{EXERCISES_PATH}/{squat}", headers=trainer, json={**body, "contraindicated_zones": ["muñeca"]})
    assert bad.status_code == 422
    good = api.put(f"{EXERCISES_PATH}/{squat}", headers=trainer, json={**body, "contraindicated_zones": ["wrist and hand"]})
    assert good.json()["contraindicated_zones"] == ["Wrist and hand"]


def test_existing_conflicts_are_reported_when_opening_and_when_assigning(client):
    api, sessions, trainer, _, sid, _template, squat, plank = setup_case(client)
    # el ejercicio ya está en la rutina y luego se lo marca como contraindicado
    api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, plank))
    api.post(path(sid, "/draft/confirm"), headers=trainer)
    api.put(f"{EXERCISES_PATH}/{plank}", headers=trainer, json=exercise_payload(contraindicated_zones=["Knee"]))
    with sessions() as db:
        db.add(ProtectedZone(student_id=sid, body_area="Knee", created_at=datetime.now(UTC)))
        db.commit()

    opened = api.get(path(sid), headers=trainer).json()
    assert [c["field"] for c in opened["conflicts"]] == ["days.0.blocks.0.exercises.1.exercise_id"]
    assert "rodilla" in opened["conflicts"][0]["message"]

    clean = create_template(api, trainer, squat, name="Limpia")
    risky = create_template(api, trainer, plank, name="Riesgosa")
    relationship_id = api.get(f"{TEMPLATES_PATH}/assignments", headers=trainer).json()[0]["relationship_id"]
    assignment = f"{TEMPLATES_PATH}/assignments/{relationship_id}"
    assert api.put(assignment, headers=trainer, json={"routine_template_id": clean["id"]}).json()["warnings"] == []
    warned = api.put(assignment, headers=trainer, json={"routine_template_id": risky["id"]}).json()
    assert warned["routine_template_id"] == risky["id"] and "Plancha" in warned["warnings"][0]
    assert api.put(assignment, headers=trainer, json={"routine_template_id": None}).json()["warnings"] == []
