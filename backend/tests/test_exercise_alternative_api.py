import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from test_routine_template_api import EXERCISES_PATH, create_exercise, exercise_payload
from test_safe_variant_api import protect, variants
from test_student_routine_api import setup_case

from backend.src.models import (
    Exercise,
    ExerciseReplacementLog,
    Notification,
    StudentRoutine,
    TrainingRelationship,
)

LOGS = "/api/v1/students/me/routine-templates/assigned/workout-logs"
REPLACE = "/api/v1/students/me/exercise-replacements"


def alts(exercise_id: str) -> str:
    return f"/api/v1/students/me/exercises/{exercise_id}/alternatives"


def body(original: str, replacement: str | None = None) -> dict:
    return {"day_name": "Día 1", "original_exercise_id": original, "replacement_exercise_id": replacement}


def case(client):
    api, sessions, trainer, student, sid, _t, squat, _plank = setup_case(client)
    press = create_exercise(api, trainer, name="Prensa", target_muscle_group="Piernas", equipment_needed="Máquina")
    return api, sessions, trainer, student, sid, squat, press


def names(response) -> list[str]:
    return [a["name"] for a in response.json()["alternatives"]]


def test_lists_same_muscle_group_only(client):
    api, _, trainer, student, _, squat, press = case(client)
    create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    gone = create_exercise(api, trainer, name="Hack", target_muscle_group=" PIERNAS ")
    api.delete(f"{EXERCISES_PATH}/{gone}", headers=trainer)
    created = create_exercise(api, trainer, name="Zancada", target_muscle_group="piernas")

    response = api.get(alts(squat), headers=student)
    assert response.status_code == 200 and names(response) == ["Prensa", "Zancada"]
    assert response.json()["can_skip"] is False
    assert {a["exercise_id"] for a in response.json()["alternatives"]} == {press, created}


def test_excludes_risky_and_shows_variant(client):
    api, sessions, trainer, student, sid, squat, press = case(client)
    api.put(f"{EXERCISES_PATH}/{press}", headers=trainer, json=exercise_payload(name="Prensa", target_muscle_group="Piernas", equipment_needed="Máquina", contraindicated_zones=["Knee"]))
    ok = create_exercise(api, trainer, name="Puente", target_muscle_group="Piernas")
    protect(sessions, sid, "Knee")

    assert names(api.get(alts(squat), headers=student)) == ["Puente"]  # Prensa es de riesgo y sin variante
    api.post(variants(press), headers=trainer, json={"variant_exercise_id": ok, "covered_zones": ["Knee"]})
    shown = {a["name"]: a for a in api.get(alts(squat), headers=student).json()["alternatives"]}
    assert shown["Prensa"]["variant"]["exercise_id"] == ok and shown["Puente"]["variant"] is None
    with sessions() as db:  # listar no abre casos ni notifica
        assert db.scalars(select(Notification)).all() == []


def test_choosing_alternative_with_variant_records_the_variant(client):
    api, sessions, trainer, student, sid, squat, press = case(client)
    api.put(f"{EXERCISES_PATH}/{press}", headers=trainer, json=exercise_payload(name="Prensa", target_muscle_group="Piernas", equipment_needed="Máquina", contraindicated_zones=["Knee"]))
    safe_ex = create_exercise(api, trainer, name="Puente", target_muscle_group="Abdominales")
    api.post(variants(press), headers=trainer, json={"variant_exercise_id": safe_ex, "covered_zones": ["Knee"]})
    protect(sessions, sid, "Knee")

    assert api.put(REPLACE, headers=student, json=body(squat, press)).json()["replacement_exercise_id"] == safe_ex
    log = {"day_name": "Día 1", "set_number": 1, "reps_completed": "10", "weight_kg": 0}
    assert api.post(LOGS, headers=student, json={**log, "exercise_id": safe_ex}).status_code == 201
    assert api.post(LOGS, headers=student, json={**log, "exercise_id": press}).status_code == 422  # no el de riesgo


def test_empty_list_allows_skip_and_records_it(client):
    api, sessions, _, student, sid, squat, press = case(client)
    with sessions() as db:
        db.get(Exercise, press).deleted_at = datetime.now(UTC)
        db.commit()
    assert api.get(alts(squat), headers=student).json() == {"alternatives": [], "can_skip": True}
    assert api.put(REPLACE, headers=student, json=body(squat)).status_code == 200
    with sessions() as db:
        log = db.scalar(select(ExerciseReplacementLog))
        assert log.replacement_exercise_id is None and log.student_id == sid


def test_replacement_is_session_only_and_overwritten(client):
    api, sessions, trainer, student, _, squat, press = case(client)
    other = create_exercise(api, trainer, name="Zancada", target_muscle_group="Piernas")
    assert api.put(REPLACE, headers=student, json=body(squat, press)).json()["replacement_exercise_id"] == press
    api.put(REPLACE, headers=student, json=body(squat, other))
    with sessions() as db:
        logs = db.scalars(select(ExerciseReplacementLog)).all()
        assert len(logs) == 1 and logs[0].replacement_exercise_id == other
        assert db.scalars(select(StudentRoutine)).all() == []  # no se crea ni se edita copia de la rutina
        assert db.scalars(select(Notification)).all() == []
    view = api.get("/api/v1/students/me/routine-templates/assigned", headers=student).json()
    assert view["days"][0]["blocks"][0]["exercises"][0]["exercise"]["id"] == squat  # la rutina no cambia


def test_sets_can_be_logged_with_replacement_only(client):
    api, _, _, student, _, squat, press = case(client)
    log = {"exercise_id": press, "day_name": "Día 1", "set_number": 1, "reps_completed": "10", "weight_kg": 50}
    assert api.post(LOGS, headers=student, json=log).status_code == 422  # sin reemplazo no pertenece a la rutina
    api.put(REPLACE, headers=student, json=body(squat, press))
    created = api.post(LOGS, headers=student, json=log)
    assert created.status_code == 201 and created.json()["exercise_id"] == press


def test_modality_does_not_change_alternatives(client):
    api, _, _, student, _, squat, _press = case(client)
    before = api.get(alts(squat), headers=student).json()
    api.put("/api/v1/students/me/routine-templates/assigned/modality", headers=student, json={"modality": "HOME"})
    assert api.get(alts(squat), headers=student).json() == before


def test_errors(client):
    api, sessions, trainer, student, _, squat, press = case(client)
    outside = create_exercise(api, trainer, name="Remo", target_muscle_group="Espalda")
    assert api.get(alts(outside), headers=student).status_code == 404
    assert api.put(REPLACE, headers=student, json=body(outside)).status_code == 404
    bad = api.put(REPLACE, headers=student, json=body(squat, outside))
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "replacement_exercise_id"
    assert api.get(alts(squat), headers=trainer).status_code == 403
    assert api.get(alts(squat)).status_code == 401
    with sessions() as db:
        db.scalar(select(TrainingRelationship)).status = "TERMINATED"
        db.commit()
    assert api.get(alts(squat), headers=student).status_code == 403
    assert api.put(REPLACE, headers=student, json=body(squat, press)).status_code == 403


def test_alternatives_response_under_two_seconds(client):  # SC-003
    api, sessions, _, student, _, squat, _press = case(client)
    with sessions() as db:
        trainer_id = db.get(Exercise, squat).trainer_id
        db.add_all(
            Exercise(trainer_id=trainer_id, name=f"Ej {i}", description="d", category="FUERZA",
                     target_muscle_group="Piernas" if i % 2 else "Espalda", equipment_needed="x",
                     created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
            for i in range(300)
        )
        db.commit()
    start = time.perf_counter()
    response = api.get(alts(squat), headers=student)
    assert response.status_code == 200 and len(response.json()["alternatives"]) == 151
    assert time.perf_counter() - start < 2


def test_replacement_chosen_before_utc_midnight_still_valid_after(client):
    api, sessions, _, student, _, squat, press = case(client)
    log = {"exercise_id": press, "day_name": "Día 1", "set_number": 1, "reps_completed": "10", "weight_kg": 50}
    api.put(REPLACE, headers=student, json=body(squat, press))

    def age(days: int) -> None:
        with sessions() as db:
            row = db.scalar(select(ExerciseReplacementLog))
            row.session_date = datetime.now(UTC).date() - timedelta(days=days)
            db.commit()

    age(1)  # elegido antes de la medianoche UTC
    assert api.post(LOGS, headers=student, json=log).status_code == 201
    age(2)
    assert api.post(LOGS, headers=student, json=log).status_code == 422
