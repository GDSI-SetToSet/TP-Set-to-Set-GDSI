from datetime import UTC, datetime

from sqlalchemy import select
from test_routine_template_api import EXERCISES_PATH, create_exercise, exercise_payload
from test_student_routine_api import draft, path, setup_case

from backend.src.models import Notification, ProtectedZone, SafeVariantCase, User


def variants(exercise_id: str, suffix: str = "") -> str:
    return f"{EXERCISES_PATH}/{exercise_id}/safe-variants{suffix}"


def resolve(exercise_id: str) -> str:
    return f"/api/v1/students/me/exercises/{exercise_id}/safe-variant"


def protect(sessions, student_id: str, *areas: str) -> None:
    with sessions() as db:
        db.add_all(ProtectedZone(student_id=student_id, body_area=a, created_at=datetime.now(UTC)) for a in areas)
        db.commit()


def risky_case(client, zones=("Knee",), student_zones=("Knee",)):
    """Alumno con la sentadilla (de riesgo) en su rutina; `lunge` es un ejercicio candidato a variante."""
    api, sessions, trainer, student, sid, _template, squat, _plank = setup_case(client)
    api.put(f"{EXERCISES_PATH}/{squat}", headers=trainer, json=exercise_payload(name="Sentadilla", contraindicated_zones=list(zones)))
    protect(sessions, sid, *student_zones)
    safe = create_exercise(api, trainer, name="Prensa liviana", video_url="https://www.youtube.com/watch?v=abcdefghijk")
    return api, sessions, trainer, student, sid, squat, safe


def case_count(sessions) -> int:
    with sessions() as db:
        return len(db.scalars(select(SafeVariantCase)).all())


def test_student_sees_safe_variant_with_video(client):
    api, _, trainer, student, _, squat, safe = risky_case(client)
    created = api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    assert created.status_code == 201 and created.json()["variant_name"] == "Prensa liviana"
    assert created.json()["covered_zones"] == ["knee"]

    body = api.get(resolve(squat), headers=student).json()
    assert body["status"] == "VARIANT" and body["variant"]["exercise_id"] == safe
    assert body["variant"]["video_url"] and body["variant"]["video_platform"] == "YOUTUBE"


def test_exercise_without_conflict_is_safe(client):
    api, _, _, student, *_ = risky_case(client, student_zones=("Shoulder",))
    squat = api.get("/api/v1/students/me/routine-templates/assigned", headers=student).json()["days"][0]["blocks"][0][
        "exercises"
    ][0]["exercise"]["id"]
    assert api.get(resolve(squat), headers=student).json() == {
        "status": "SAFE", "variant": None, "message": None, "can_skip": False,
    }


def test_blocked_notifies_trainer_once_and_reopens_after_resolution(client):
    api, sessions, trainer, student, _, squat, safe = risky_case(client)
    first = api.get(resolve(squat), headers=student).json()
    assert first["status"] == "BLOCKED" and first["can_skip"] is True and first["variant"] is None
    api.get(resolve(squat), headers=student)
    with sessions() as db:
        notes = db.scalars(select(Notification)).all()
        trainer_user = db.scalar(select(User).where(User.email == "coach@example.com"))
        assert len(notes) == 1 and notes[0].recipient_id == trainer_user.id
        assert notes[0].type == "SAFE_VARIANT_MISSING" and "Sentadilla" in notes[0].message
    listed = api.get("/api/v1/trainers/me/notifications", headers=trainer).json()
    assert listed["total"] == 1

    api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    with sessions() as db:
        assert db.scalar(select(SafeVariantCase)).status == "RESOLVED"
    assert api.get(resolve(squat), headers=student).json()["status"] == "VARIANT"

    # cambia la cobertura (se quita la variante): el caso se reabre y avisa de nuevo
    link = api.get(variants(squat), headers=trainer).json()[0]["id"]
    assert api.delete(variants(squat, f"/{link}"), headers=trainer).status_code == 204
    assert api.get(resolve(squat), headers=student).json()["status"] == "BLOCKED"
    with sessions() as db:
        assert len(db.scalars(select(Notification)).all()) == 2 and db.scalar(select(SafeVariantCase)).status == "PENDING"


def test_variant_must_cover_all_student_zones(client):
    api, _, trainer, student, _, squat, safe = risky_case(client, zones=("Knee", "Shoulder"), student_zones=("Knee", "Shoulder"))
    api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    assert api.get(resolve(squat), headers=student).json()["status"] == "BLOCKED"
    link = api.get(variants(squat), headers=trainer).json()[0]["id"]
    assert api.put(variants(squat, f"/{link}"), headers=trainer, json={"covered_zones": ["Knee", "Shoulder"]}).status_code == 200
    assert api.get(resolve(squat), headers=student).json()["status"] == "VARIANT"


def test_variant_contraindicated_for_another_student_zone_is_not_offered(client):
    api, _, trainer, student, _, squat, safe = risky_case(client, zones=("Knee",), student_zones=("Knee", "Shoulder"))
    api.put(f"{EXERCISES_PATH}/{safe}", headers=trainer, json=exercise_payload(name="Prensa", contraindicated_zones=["Shoulder"]))
    api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    assert api.get(resolve(squat), headers=student).json()["status"] == "BLOCKED"


def test_deleted_variant_exercise_is_not_offered(client):
    api, _, trainer, student, _, squat, safe = risky_case(client)
    api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    api.delete(f"{EXERCISES_PATH}/{safe}", headers=trainer)
    assert api.get(resolve(squat), headers=student).json()["status"] == "BLOCKED"


def test_oldest_valid_variant_wins(client):
    api, _, trainer, student, _, squat, safe = risky_case(client)
    other = create_exercise(api, trainer, name="Otra variante")
    for variant in (safe, other):
        api.post(variants(squat), headers=trainer, json={"variant_exercise_id": variant, "covered_zones": ["Knee"]})
    assert api.get(resolve(squat), headers=student).json()["variant"]["exercise_id"] == safe


def test_variant_validation_errors(client):
    api, _, trainer, _, _, squat, safe = risky_case(client)
    other_trainer_headers = trainer
    body = {"variant_exercise_id": safe, "covered_zones": ["Knee"]}
    assert api.post(variants(squat), headers=trainer, json={**body, "covered_zones": ["Hip"]}).status_code == 422
    assert api.post(variants(squat), headers=trainer, json={**body, "covered_zones": []}).status_code == 422
    assert api.post(variants(squat), headers=trainer, json={**body, "variant_exercise_id": squat}).status_code == 422
    assert api.post(variants(squat), headers=trainer, json={**body, "variant_exercise_id": "nope"}).status_code == 422
    api.put(f"{EXERCISES_PATH}/{safe}", headers=trainer, json=exercise_payload(name="Prensa", contraindicated_zones=["Knee"]))
    assert api.post(variants(squat), headers=trainer, json=body).status_code == 422
    api.put(f"{EXERCISES_PATH}/{safe}", headers=trainer, json=exercise_payload(name="Prensa"))
    assert api.post(variants(squat), headers=other_trainer_headers, json=body).status_code == 201
    assert api.post(variants(squat), headers=trainer, json=body).status_code == 409
    assert api.put(variants(squat, "/missing"), headers=trainer, json={"covered_zones": ["Knee"]}).status_code == 404
    assert api.get(variants("missing"), headers=trainer).status_code == 404


def test_student_access_rules(client):
    api, sessions, trainer, student, _, squat, _safe = risky_case(client)
    outside = create_exercise(api, trainer, name="Fuera de rutina", contraindicated_zones=["Knee"])
    assert api.get(resolve(outside), headers=student).status_code == 404
    assert api.get(resolve("missing"), headers=student).status_code == 404
    assert api.get(resolve(squat), headers=trainer).status_code in (403, 404)  # un entrenador no usa la vista del alumno
    # el borrador no cuenta como rutina vigente
    api.put(path(_sid(sessions), "/draft"), headers=trainer, json=draft(0, squat, outside))
    assert api.get(resolve(outside), headers=student).status_code == 404


def _sid(sessions) -> str:
    from backend.src.models import StudentProfile

    with sessions() as db:
        return db.scalar(select(StudentProfile.id))


def test_student_without_active_link_gets_403(client):
    api, sessions, _trainer, student, _, squat, _ = risky_case(client)
    from backend.src.models import TrainingRelationship

    with sessions() as db:
        db.scalar(select(TrainingRelationship)).status = "TERMINATED"
        db.commit()
    assert api.get(resolve(squat), headers=student).status_code == 403


def test_trainer_views_do_not_open_cases_or_notify(client):
    api, sessions, trainer, _, sid, squat, safe = risky_case(client)
    api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    assert api.get(path(sid), headers=trainer).status_code == 200
    blocked = api.put(path(sid, "/draft"), headers=trainer, json=draft(0, squat, safe))
    assert blocked.status_code == 422
    api.delete(variants(squat, f"/{api.get(variants(squat), headers=trainer).json()[0]['id']}"), headers=trainer)
    api.get(path(sid), headers=trainer)
    assert case_count(sessions) == 0
    with sessions() as db:
        assert db.scalars(select(Notification)).all() == []


def test_us14_conflicts_offer_resolved_safe_variant(client):
    api, _, trainer, _, sid, squat, safe = risky_case(client)
    assert api.get(path(sid), headers=trainer).json()["conflicts"][0]["safe_variant"] is None
    api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    conflict = api.get(path(sid), headers=trainer).json()["conflicts"][0]
    assert conflict["safe_variant"] == {"exercise_id": safe, "name": "Prensa liviana"}
    assert "Prensa liviana" in conflict["message"]


LOGS_PATH = "/api/v1/students/me/routine-templates/assigned/workout-logs"


def log_set(api, student, exercise_id: str, set_number: int = 1):
    return api.post(
        LOGS_PATH,
        headers=student,
        json={"exercise_id": exercise_id, "day_name": "Día 1", "set_number": set_number, "reps_completed": "8", "weight_kg": 20},
    )


def test_cannot_log_sets_for_exercise_without_safe_variant(client):
    api, sessions, trainer, student, _, squat, safe = risky_case(client)
    blocked = log_set(api, student, squat)
    assert blocked.status_code == 422 and "variante segura" in blocked.json()["detail"]
    assert blocked.json()["errors"][0]["field"] == "exercise_id"
    assert api.get(LOGS_PATH, headers=student).json() == []
    with sessions() as db:  # el intento también avisa al entrenador (una sola vez)
        assert len(db.scalars(select(Notification)).all()) == 1

    # con una variante que cubre sus zonas el ejercicio deja de estar bloqueado
    api.post(variants(squat), headers=trainer, json={"variant_exercise_id": safe, "covered_zones": ["Knee"]})
    assert log_set(api, student, squat).status_code == 201


def test_logging_exercise_without_risk_is_unaffected(client):
    api, _, _, student, *_ = risky_case(client, student_zones=("Shoulder",))
    squat = api.get("/api/v1/students/me/routine-templates/assigned", headers=student).json()["days"][0]["blocks"][0][
        "exercises"
    ][0]["exercise"]["id"]
    assert log_set(api, student, squat).status_code == 201
