"""Regression tests covering all Sprint 6 and product stabilization audit findings (AUD-01..AUD-25)."""

import io
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.scripts.seed_demo import clean_demo_data, seed_demo_data
from backend.src.core.database import Base
from backend.src.core.migrations import TARGET_CHECK_CONSTRAINTS, apply_migrations
from backend.src.models.achievement import AchievementCongratulation, StudentAchievement
from backend.src.models.assigned_routine import AssignedRoutine
from backend.src.models.body_map_report import BodyMapPainReport
from backend.src.models.exercise import Exercise
from backend.src.models.informal_payment import InformalPayment
from backend.src.models.notification import Notification
from backend.src.models.personal_record import PersonalRecord
from backend.src.models.safety_alert import SafetyAlert
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.services.achievement_service import CATALOG, evaluate_achievements
from backend.src.services.streak_service import monday
from backend.tests.test_us60_rpe_api import (
    ASSIGNED_PATH,
    TEMPLATES_PATH,
    register_and_login,
    setup_routine_and_assignment,
)

PDF_BYTES = b"%PDF-1.4 comprobante valido\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _today() -> date:
    return datetime.now(UTC).date()


def _create_second_exercise(sessions, trainer_email: str, name: str = "Remo con barra") -> str:
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        now = _now()
        exercise = Exercise(
            trainer_id=trainer_user.trainer_profile.id,
            name=name,
            description="Ejercicio alternativo de prueba",
            category="STRENGTH",
            target_muscle_group="Espalda",
            equipment_needed="Sin equipamiento",
            has_no_materials_alternative=True,
            contraindicated_zones=[],
            created_at=now,
            updated_at=now,
        )
        db.add(exercise)
        db.commit()
        return exercise.id


def test_aud01_and_aud02_expired_block_across_endpoints_preserves_readonly(client):
    api, sessions = client
    trainer = register_and_login(api, "aud01_t@example.com", "TRAINER")
    student = register_and_login(api, "aud01_s@example.com", "STUDENT")
    exercise_id, relationship_id, _routine_id = setup_routine_and_assignment(
        api, sessions, trainer, "aud01_s@example.com", trainer_email="aud01_t@example.com"
    )
    alt_id = _create_second_exercise(sessions, "aud01_t@example.com")

    # Crear sesión y serie válidas antes de vencer.
    session_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
    assert session_res.status_code == 201
    open_session_id = session_res.json()["id"]
    log_res = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 40,
            "session_id": open_session_id,
        },
    )
    assert log_res.status_code == 201
    log_id = log_res.json()["id"]

    # Vencer la suscripción moviendo start_date hacia atrás (y agregar rutina IA aprobada para cubrir /assigned-routine).
    with sessions() as db:
        rel = db.get(TrainingRelationship, relationship_id)
        rel.start_date = _today() - timedelta(days=45)
        db.add(
            AssignedRoutine(
                trainer_id=rel.trainer_id,
                student_id=rel.student_id,
                name="Rutina IA Test",
                duration_weeks=4,
                intensity="MEDIA",
                status="APPROVED",
                approved_at=_now(),
                created_at=_now(),
                updated_at=_now(),
            )
        )
        db.commit()

    # Todos los endpoints operativos deben bloquear con 409.
    assert api.get(ASSIGNED_PATH, headers=student).status_code == 409
    assert api.get("/api/v1/students/me/assigned-routine", headers=student).status_code == 409
    assert api.put(f"{ASSIGNED_PATH}/modality", headers=student, json={"modality": "HOME"}).status_code == 409
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).status_code == 409
    assert (
        api.post(
            f"{ASSIGNED_PATH}/workout-logs",
            headers=student,
            json={
                "exercise_id": exercise_id,
                "day_name": "Día 1",
                "set_number": 2,
                "reps_completed": "10",
                "weight_kg": 40,
                "session_id": None,
            },
        ).status_code
        == 409
    )
    assert (
        api.post(
            f"{ASSIGNED_PATH}/workout-logs",
            headers=student,
            json={
                "exercise_id": exercise_id,
                "day_name": "Día 1",
                "set_number": 2,
                "reps_completed": "10",
                "weight_kg": 40,
                "session_id": open_session_id,
            },
        ).status_code
        == 409
    )
    assert api.delete(f"{ASSIGNED_PATH}/workout-logs/{log_id}", headers=student).status_code == 409
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{open_session_id}/finish", headers=student, json={}).status_code == 409
    assert (
        api.put(
            "/api/v1/students/me/exercise-replacements",
            headers=student,
            json={
                "day_name": "Día 1",
                "original_exercise_id": exercise_id,
                "replacement_exercise_id": alt_id,
                "session_id": open_session_id,
            },
        ).status_code
        == 409
    )
    assert (
        api.post(
            f"/api/v1/conversations/{relationship_id}/technical-queries",
            headers=student,
            json={"exercise_id": exercise_id, "body": "¿Cómo hago?"},
        ).status_code
        == 409
    )

    # Lecturas históricas y comunicación permanecen accesibles (AUD-02).
    assert api.get(f"{ASSIGNED_PATH}/workout-logs", headers=student).status_code == 200
    assert api.get(f"{ASSIGNED_PATH}/workout-sessions", headers=student).status_code == 200
    assert api.get("/api/v1/students/me/body-map-reports", headers=student).status_code == 200
    assert api.get(f"{ASSIGNED_PATH}/effort-feedback", headers=student).status_code == 200
    assert api.get("/api/v1/students/me/progress", headers=student).status_code == 200
    assert api.get("/api/v1/conversations", headers=student).status_code == 200
    assert api.get(f"/api/v1/students/me/subscriptions/{relationship_id}/payments", headers=student).status_code == 200


def test_aud03_date_drift_validation(client):
    api, sessions = client
    trainer = register_and_login(api, "aud03_t@example.com", "TRAINER")
    student = register_and_login(api, "aud03_s@example.com", "STUDENT")
    setup_routine_and_assignment(api, sessions, trainer, "aud03_s@example.com", trainer_email="aud03_t@example.com")

    too_far_future = (_today() + timedelta(days=3)).isoformat()
    too_far_past = (_today() - timedelta(days=3)).isoformat()
    within_drift = (_today() - timedelta(days=1)).isoformat()

    assert api.get("/api/v1/students/me/subscriptions", params={"date": too_far_future}, headers=student).status_code == 422
    assert api.get("/api/v1/trainers/me/subscriptions", params={"date": too_far_past}, headers=trainer).status_code == 422
    assert api.get("/api/v1/students/me/subscriptions", params={"date": within_drift}, headers=student).status_code == 200


def test_aud04_receipt_magic_bytes_sanitization_limit_and_rollback_cleanup(client, tmp_path, monkeypatch):
    api, sessions = client
    receipts_dir = tmp_path / "aud04_receipts"
    monkeypatch.setattr("backend.src.services.student_subscription_service.RECEIPTS_DIR", receipts_dir)

    trainer = register_and_login(api, "aud04_t@example.com", "TRAINER")
    student = register_and_login(api, "aud04_s@example.com", "STUDENT")
    _, relationship_id, _ = setup_routine_and_assignment(
        api, sessions, trainer, "aud04_s@example.com", trainer_email="aud04_t@example.com"
    )
    today_iso = _today().isoformat()
    pay_url = f"/api/v1/students/me/subscriptions/{relationship_id}/payments"

    # MIME spoofing (HTML con Content-Type application/pdf) -> 422.
    spoof = api.post(
        pay_url,
        headers=student,
        data={"paid_on": today_iso, "amount": "15000.00", "method": "TRANSFERENCIA", "months_covered": "1"},
        files={"receipt": ("evil.pdf", io.BytesIO(b"<html><script>alert(1)</script></html>"), "application/pdf")},
    )
    assert spoof.status_code == 422

    # Nombre con path traversal + PNG válido -> sanitizado + nosniff.
    valid = api.post(
        pay_url,
        headers=student,
        data={"paid_on": today_iso, "amount": "15000.00", "method": "TRANSFERENCIA", "months_covered": "1"},
        files={"receipt": ("../../<script>comprobante.png", io.BytesIO(PNG_BYTES), "image/png")},
    )
    assert valid.status_code == 201
    payment = valid.json()["payment"]
    assert ".." not in payment["receipt_filename"]
    assert "<" not in payment["receipt_filename"]

    dl = api.get(f"/api/v1/payments/{payment['id']}/receipt", headers=trainer)
    assert dl.status_code == 200
    assert dl.headers.get("X-Content-Type-Options") == "nosniff"

    # Rollback en BD debe borrar archivo huérfano del disco.
    files_before = set(receipts_dir.rglob("*"))
    from sqlalchemy.orm import Session as OrmSession

    orig_commit = OrmSession.commit

    def fail_commit(self):
        raise RuntimeError("boom commit")

    monkeypatch.setattr(OrmSession, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        api.post(
            pay_url,
            headers=student,
            data={"paid_on": today_iso, "amount": "15000.00", "method": "EFECTIVO", "months_covered": "1"},
            files={"receipt": ("recibo.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
        )
    monkeypatch.setattr(OrmSession, "commit", orig_commit)
    assert set(receipts_dir.rglob("*")) == files_before

    # Límite máximo de 5 pagos pendientes por vínculo.
    for _ in range(4):
        ok = api.post(
            pay_url,
            headers=student,
            data={"paid_on": today_iso, "amount": "15000.00", "method": "EFECTIVO", "months_covered": "1"},
        )
        assert ok.status_code == 201
    sixth = api.post(
        pay_url,
        headers=student,
        data={"paid_on": today_iso, "amount": "15000.00", "method": "EFECTIVO", "months_covered": "1"},
    )
    assert sixth.status_code == 422


def test_aud05_aud06_aud16_aud23_queries_history_notes_guard_and_read_sync(client):
    api, sessions = client
    trainer = register_and_login(api, "aud05_t@example.com", "TRAINER")
    student = register_and_login(api, "aud05_s@example.com", "STUDENT")
    other_student = register_and_login(api, "aud05_other@example.com", "STUDENT")
    exercise_id, relationship_id, _ = setup_routine_and_assignment(
        api, sessions, trainer, "aud05_s@example.com", trainer_email="aud05_t@example.com"
    )
    _, other_rel, _ = setup_routine_and_assignment(
        api, sessions, trainer, "aud05_other@example.com", trainer_email="aud05_t@example.com"
    )
    student_id = sessions().get(TrainingRelationship, relationship_id).student_id

    sess = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    other_sess = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=other_student, json={"day_name": "Día 1"}).json()

    # Consulta técnica del alumno genera notificación TECHNICAL_QUERY al entrenador.
    q = api.post(
        f"/api/v1/conversations/{relationship_id}/technical-queries",
        headers=student,
        json={"exercise_id": exercise_id, "body": "¿Cómo ubico los pies?", "session_id": sess["id"], "set_number": 1},
    )
    assert q.status_code == 201
    q_id = q.json()["id"]

    # Responder fijando nota técnica marca notificación como leída (AUD-23) y mueve consulta a historial (AUD-05).
    rep = api.post(
        f"/api/v1/conversations/{relationship_id}/messages",
        headers=trainer,
        json={"body": "Pies al ancho de hombros", "reply_to_message_id": q_id, "pin_as_technical_note": True},
    )
    assert rep.status_code == 201

    with sessions() as db:
        trainer_user_id = db.scalar(select(User.id).where(User.email == "aud05_t@example.com"))
        tq_notifs = list(
            db.scalars(
                select(Notification).where(
                    Notification.recipient_id == trainer_user_id,
                    Notification.type == "TECHNICAL_QUERY",
                    Notification.related_entity_id == q_id,
                )
            )
        )
        assert len(tq_notifs) == 1
        assert tq_notifs[0].is_read is True

    # Bandeja pendiente vacía, pero historial contiene hilo completo (AUD-05).
    assert api.get("/api/v1/trainers/me/technical-queries", headers=trainer).json() == []
    hist = api.get(
        "/api/v1/trainers/me/technical-queries/history",
        params={"student_id": student_id},
        headers=trainer,
    )
    assert hist.status_code == 200
    groups = hist.json()
    assert len(groups) == 1
    assert len(groups[0]["threads"]) == 1
    assert groups[0]["threads"][0]["query"]["id"] == q_id
    assert len(groups[0]["threads"][0]["replies"]) == 1
    assert groups[0]["threads"][0]["replies"][0]["technical_note"] is not None
    assert "id" in groups[0]["threads"][0]["replies"][0]["technical_note"]

    # Nota técnica pendiente bloquea POST workout-logs en backend con 409 (AUD-06).
    blocked_log = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 40,
            "session_id": sess["id"],
        },
    )
    assert blocked_log.status_code == 409

    # Confirmar nota con session_id ajeno -> 422; con UUID > 36 chars -> 422 (AUD-16).
    notes = api.get("/api/v1/students/me/technical-notes", headers=student).json()
    note_id = notes[0]["id"]
    assert (
        api.post(
            f"/api/v1/students/me/technical-notes/{note_id}/acknowledge",
            headers=student,
            json={"session_id": other_sess["id"]},
        ).status_code
        == 422
    )
    assert (
        api.post(
            f"/api/v1/students/me/technical-notes/{note_id}/acknowledge",
            headers=student,
            json={"session_id": "x" * 50},
        ).status_code
        == 422
    )

    # Confirmar con sesión propia desbloquea el registro.
    ack = api.post(
        f"/api/v1/students/me/technical-notes/{note_id}/acknowledge",
        headers=student,
        json={"session_id": sess["id"]},
    )
    assert ack.status_code == 200
    allowed_log = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "exercise_id": exercise_id,
            "day_name": "Día 1",
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 40,
            "session_id": sess["id"],
        },
    )
    assert allowed_log.status_code == 201

    # Ejercicio soft-deleted todavía asignado permite enviar consulta técnica (AUD-23).
    with sessions() as db:
        ex = db.get(Exercise, exercise_id)
        ex.deleted_at = _now()
        db.commit()
    assert other_rel != relationship_id
    q2 = api.post(
        f"/api/v1/conversations/{relationship_id}/technical-queries",
        headers=student,
        json={"exercise_id": exercise_id, "body": "Consulta tras archivado", "session_id": sess["id"]},
    )
    assert q2.status_code == 201


def test_aud08_aud15_aud25_unified_pr_rule_recompute_and_trainer_achievements(client):
    api, sessions = client
    trainer = register_and_login(api, "aud08_t@example.com", "TRAINER")
    student = register_and_login(api, "aud08_s@example.com", "STUDENT")
    exercise_id, relationship_id, _ = setup_routine_and_assignment(
        api, sessions, trainer, "aud08_s@example.com", trainer_email="aud08_t@example.com"
    )
    bodyweight_ex = _create_second_exercise(sessions, "aud08_t@example.com", name="Flexiones")
    with sessions() as db:
        student_id = db.get(TrainingRelationship, relationship_id).student_id

    # Sesión 1: baseline -> NO debe contar como PR en ningún servicio ni crear PersonalRecord.
    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    l1 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={"exercise_id": exercise_id, "day_name": "Día 1", "set_number": 1, "reps_completed": "8", "weight_kg": 0, "session_id": s1["id"]},
    )
    assert l1.status_code == 201
    assert l1.json()["is_personal_record"] is False
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={}).status_code == 200
    assert api.get(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/summary", headers=student).json()["personal_records"] == []
    assert [a["code"] for a in api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=trainer).json()["unlocked"]] == ["FIRST_SESSION"]

    # Sesión 2: mismo peso (0 kg bodyweight) con más repeticiones (12 > 8) -> SÍ es PR en todos lados!
    s2 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    l2 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={"exercise_id": exercise_id, "day_name": "Día 1", "set_number": 1, "reps_completed": "12", "weight_kg": 0, "session_id": s2["id"]},
    )
    assert l2.status_code == 201
    assert l2.json()["is_personal_record"] is True
    l2_id = l2.json()["id"]

    # Sesión activa sin finalizar no desbloquea FIRST_PR retrospectivo si borramos l2, pero tras finalizar SÍ desbloquea incluso al consultar entrenador primero (AUD-15).
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s2['id']}/finish", headers=student, json={}).status_code == 200
    trainer_ach = api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=trainer).json()
    unlocked_by_code = {a["code"]: a for a in trainer_ach["unlocked"]}
    assert "FIRST_PR" in unlocked_by_code
    assert "mejor marca" in unlocked_by_code["FIRST_PR"]["description"]  # AUD-25
    assert "mejor marca" in CATALOG[1].description or any("mejor marca" in c.description for c in CATALOG)

    progress = api.get("/api/v1/students/me/progress", headers=student).json()
    assert len(progress["records"]) == 1
    assert progress["records"][0]["reps"] == 12

    # Borrar log PR elimina notificación PERSONAL_RECORD y recomputa/limpia PersonalRecord.
    # Primero creamos una sesión 3 antes de probar eliminación de PR de sesión 3.
    s3 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    l3 = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={"exercise_id": exercise_id, "day_name": "Día 1", "set_number": 1, "reps_completed": "15", "weight_kg": 0, "session_id": s3["id"]},
    ).json()
    assert l3["is_personal_record"] is True
    assert api.delete(f"{ASSIGNED_PATH}/workout-logs/{l3['id']}", headers=student).status_code == 204
    with sessions() as db:
        trainer_user_id = db.scalar(select(User.id).where(User.email == "aud08_t@example.com"))
        orphan = db.scalar(
            select(Notification).where(
                Notification.recipient_id == trainer_user_id,
                Notification.type == "PERSONAL_RECORD",
                Notification.related_entity_id == l3["id"],
            )
        )
        assert orphan is None
        pr = db.scalar(select(PersonalRecord).where(PersonalRecord.student_id == student_id, PersonalRecord.exercise_id == exercise_id))
        assert pr is not None
        assert pr.workout_set_log_id == l2_id
    assert bodyweight_ex != exercise_id


def test_aud09_aud10_aud11_aud14_aud22_multi_trainer_congrats_streaks_and_concurrency(client):
    api, sessions = client
    trainer_a = register_and_login(api, "aud10_ta@example.com", "TRAINER")
    trainer_b = register_and_login(api, "aud10_tb@example.com", "TRAINER")
    student = register_and_login(api, "aud10_s@example.com", "STUDENT")

    ex_a, rel_a, routine_a = setup_routine_and_assignment(
        api, sessions, trainer_a, "aud10_s@example.com", trainer_email="aud10_ta@example.com"
    )
    # También creamos un segundo entrenador activo con su propia rutina para el mismo alumno.
    ex_b_res = api.post(
        "/api/v1/exercises",
        headers=trainer_b,
        json={
            "name": "Peso muerto",
            "description": "Bisagra de cadera",
            "category": "FUERZA",
            "target_muscle_group": "Espalda",
            "equipment_needed": "Barra",
        },
    )
    assert ex_b_res.status_code == 201
    ex_b = ex_b_res.json()["id"]
    with sessions() as db:
        db.get(TrainingRelationship, rel_a).start_date = _today() - timedelta(days=20)
        tb_user = db.scalar(select(User).where(User.email == "aud10_tb@example.com"))
        st_user = db.scalar(select(User).where(User.email == "aud10_s@example.com"))
        tb_plan = TrainingPlan(
            trainer_id=tb_user.trainer_profile.id,
            title="Plan B",
            monthly_price=25000,
            currency="ARS",
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(tb_plan)
        db.flush()
        rel_b_obj = TrainingRelationship(
            student_id=st_user.student_profile.id,
            trainer_id=tb_user.trainer_profile.id,
            plan_id=tb_plan.id,
            agreed_monthly_price=25000,
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=_today(),
        )
        db.add(rel_b_obj)
        db.commit()
        rel_b = rel_b_obj.id
    tpl_b_res = api.post(
        TEMPLATES_PATH,
        headers=trainer_b,
        json={
            "name": "Rutina B Initial",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": "Día 1",
                    "blocks": [
                        {
                            "name": "Base",
                            "exercises": [
                                {"exercise_id": ex_b, "sets": 3, "reps": "10", "rest_seconds": 60, "target_weight_kg": 15}
                            ],
                        }
                    ],
                }
            ],
        },
    )
    assert tpl_b_res.status_code == 201
    routine_b = tpl_b_res.json()["id"]
    assert api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_b}",
        headers=trainer_b,
        json={"routine_template_id": routine_b},
    ).status_code == 200

    # Completar sesión en rel_a y desbloquear logro (evaluar 2 veces seguidas idempotentemente -> AUD-09).
    s1 = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{s1['id']}/finish", headers=student, json={}).status_code == 200

    with sessions() as db:
        rel_obj = db.get(TrainingRelationship, rel_a)
        evaluate_achievements(db, rel_obj.student)
        evaluate_achievements(db, rel_obj.student)
        db.commit()
        student_id = rel_obj.student_id
        achievements = list(db.scalars(select(StudentAchievement).where(StudentAchievement.student_id == student_id)))
        assert len(achievements) == 1
        ach_id = achievements[0].id

    # Ambos entrenadores felicitan el mismo logro de forma aislada (AUD-10).
    c1 = api.post(f"/api/v1/trainers/me/achievements/{ach_id}/congratulation", headers=trainer_a, json={"message": "¡Grande Coach A!"})
    c2 = api.post(f"/api/v1/trainers/me/achievements/{ach_id}/congratulation", headers=trainer_b, json={"message": "¡Bien hecho Coach B!"})
    assert c1.status_code == 201
    assert c2.status_code == 201
    # Duplicado del mismo entrenador devuelve 409 (AUD-09).
    assert api.post(f"/api/v1/trainers/me/achievements/{ach_id}/congratulation", headers=trainer_a, json={"message": "Otra"}).status_code == 409

    # Cada entrenador ve solo SU felicitación, nunca la del colega (AUD-10).
    ta_list = api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=trainer_a).json()["unlocked"]
    tb_list = api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=trainer_b).json()["unlocked"]
    assert ta_list[0]["congratulation"]["message"] == "¡Grande Coach A!"
    assert tb_list[0]["congratulation"]["message"] == "¡Bien hecho Coach B!"
    with sessions() as db:
        student_user_id = db.scalar(select(User.id).where(User.email == "aud10_s@example.com"))
        cong_notifs = list(db.scalars(select(Notification).where(Notification.recipient_id == student_user_id, Notification.type == "CONGRATULATION")))
        assert len(cong_notifs) == 2
        assert all("Mi evolución" in n.message for n in cong_notifs)  # AUD-22
        assert db.scalar(select(func.count(AchievementCongratulation.id)).where(AchievementCongratulation.achievement_id == ach_id)) == 2

    # AUD-11 + AUD-14: sesiones pasadas en rel_b preservan racha al cambiar rutina y coinciden entre streak y progress.
    cur_mon = monday(_today())
    with sessions() as db:
        r_b = db.get(TrainingRelationship, rel_b)
        r_b.routine_assigned_at = datetime.combine(cur_mon - timedelta(weeks=3), datetime.min.time())
        for wk in (3, 2, 1):
            ws = WorkoutSession(
                student_id=r_b.student_id,
                relationship_id=r_b.id,
                routine_id=routine_b,
                day_name="Día 1",
                modality="GYM",
                weekly_target=1,
                started_at=datetime.combine(cur_mon - timedelta(weeks=wk), datetime.min.time()) + timedelta(hours=10),
                finished_at=datetime.combine(cur_mon - timedelta(weeks=wk), datetime.min.time()) + timedelta(hours=11),
            )
            db.add(ws)
        db.commit()

        db.commit()

    # Reasignar nueva rutina con 3 días por semana ahora NO debe borrar la racha previa (AUD-11).
    new_tpl_res = api.post(
        TEMPLATES_PATH,
        headers=trainer_b,
        json={
            "name": "Nueva Rutina 3D",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": f"Día {i}",
                    "blocks": [
                        {
                            "name": "Principal",
                            "exercises": [
                                {"exercise_id": ex_b, "sets": 3, "reps": "10", "rest_seconds": 60, "target_weight_kg": 15}
                            ],
                        }
                    ],
                }
                for i in (1, 2, 3)
            ],
        },
    )
    assert new_tpl_res.status_code == 201
    reassigned = api.put(
        f"{TEMPLATES_PATH}/assignments/{rel_b}",
        headers=trainer_b,
        json={"routine_template_id": new_tpl_res.json()["id"]},
    )
    assert reassigned.status_code == 200

    streak_res = api.get("/api/v1/students/me/streak", headers=student)
    progress_res = api.get("/api/v1/students/me/progress", headers=student)
    assert streak_res.status_code == 200
    assert progress_res.status_code == 200
    assert streak_res.json()["current_weeks"] == 3
    assert progress_res.json()["summary"]["streak"]["current_weeks"] == streak_res.json()["current_weeks"]
    assert progress_res.json()["summary"]["streak"]["best_weeks"] == streak_res.json()["max_weeks"]
    assert ex_a != ex_b and routine_a != routine_b


def test_aud12_aud13_aud17_termination_cleanup_readonly_payments_and_notification_routing(client, tmp_path, monkeypatch):
    api, sessions = client
    receipts_dir = tmp_path / "aud17_receipts"
    monkeypatch.setattr("backend.src.services.student_subscription_service.RECEIPTS_DIR", receipts_dir)

    trainer = register_and_login(api, "aud12_t@example.com", "TRAINER")
    student = register_and_login(api, "aud12_s@example.com", "STUDENT")
    _, relationship_id, _ = setup_routine_and_assignment(
        api, sessions, trainer, "aud12_s@example.com", trainer_email="aud12_t@example.com"
    )
    with sessions() as db:
        rel = db.get(TrainingRelationship, relationship_id)
        rel.start_date = _today() - timedelta(days=5)
        db.commit()
        student_id = rel.student_id

    today_iso = _today().isoformat()
    # Sesión activa antes de baja.
    sess = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()

    # Pago confirmado (verifica AUD-13 related_entity_id=relationship_id) + segundo pago pendiente con comprobante.
    p1 = api.post(
        f"/api/v1/students/me/subscriptions/{relationship_id}/payments",
        headers=student,
        data={"paid_on": today_iso, "amount": "20000.00", "method": "TRANSFERENCIA", "months_covered": "1"},
        files={"receipt": ("p1.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    ).json()["payment"]
    assert api.post(f"/api/v1/trainers/me/payments/{p1['id']}/confirm", headers=trainer).status_code == 200

    p2 = api.post(
        f"/api/v1/students/me/subscriptions/{relationship_id}/payments",
        headers=student,
        data={"paid_on": today_iso, "amount": "20000.00", "method": "TRANSFERENCIA", "months_covered": "1"},
    ).json()["payment"]

    with sessions() as db:
        student_user_id = db.scalar(select(User.id).where(User.email == "aud12_s@example.com"))
        confirmed_notif = db.scalar(
            select(Notification).where(Notification.recipient_id == student_user_id, Notification.type == "PAYMENT_CONFIRMED")
        )
        assert confirmed_notif.related_entity_id == relationship_id  # AUD-13

    # Dar de baja en fecha anterior a start_date -> 422 (AUD-12).
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).start_date = _today()
        db.commit()
    bad_term = api.post(
        f"/api/v1/trainers/me/students/{student_id}/termination",
        params={"date": (_today() - timedelta(days=1)).isoformat()},
        headers=trainer,
        json={"category": "RAZONES_PERSONALES"},
    )
    assert bad_term.status_code == 422

    term = api.post(
        f"/api/v1/trainers/me/students/{student_id}/termination",
        headers=trainer,
        json={"category": "RAZONES_PERSONALES"},
    )
    assert term.status_code == 200

    # Pago pendiente p2 auto-rechazado al dar de baja (AUD-12).
    with sessions() as db:
        p2_db = db.get(InformalPayment, p2["id"])
        assert p2_db.status == "RECHAZADO"

    # Sesiones y reportes asociados a sesión de vínculo TERMINATED rechazados con 409 (AUD-12).
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{sess['id']}/finish", headers=student, json={}).status_code == 409
    assert api.patch(f"{ASSIGNED_PATH}/workout-sessions/{sess['id']}/rpe", headers=student, json={"rpe": 7}).status_code == 409
    assert (
        api.post(
            "/api/v1/body-map-reports",
            headers=student,
            json={"context": "POST_SESSION", "session_id": sess["id"], "zones": [{"zone": "knee", "intensity": "PAIN"}]},
        ).status_code
        == 409
    )

    # Reporte general sin session_id tras la baja NO debe quedar bloqueado por un vínculo TERMINATED pasado (AUD-12).
    general_report = api.post(
        "/api/v1/body-map-reports",
        headers=student,
        json={"context": "POST_SESSION", "session_id": None, "zones": [{"zone": "knee", "intensity": "PAIN"}]},
    )
    assert general_report.status_code == 201
    with sessions() as db:
        saved_report = db.get(BodyMapPainReport, general_report.json()["id"])
        assert saved_report is not None
        assert saved_report.relationship_id is None
        assert db.scalar(select(func.count(SafetyAlert.id))) == 0

    # Historial y comprobantes legibles tras la baja para ambos (AUD-17), pero mutaciones 404.
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/payments", headers=trainer).status_code == 200
    assert api.get(f"/api/v1/students/me/subscriptions/{relationship_id}/payments", headers=student).status_code == 200
    assert api.get(f"/api/v1/payments/{p1['id']}/receipt", headers=trainer).status_code == 200
    assert api.get(f"/api/v1/payments/{p1['id']}/receipt", headers=student).status_code == 200
    assert api.post(f"/api/v1/trainers/me/payments/{p1['id']}/void", headers=trainer, json={"reason": "Anular post baja"}).status_code == 404
    assert (
        api.post(
            f"/api/v1/students/me/subscriptions/{relationship_id}/payments",
            headers=student,
            data={"paid_on": today_iso, "amount": "20000.00", "method": "EFECTIVO", "months_covered": "1"},
        ).status_code
        == 404
    )


def test_aud16_sqlite_migrations_add_conversation_and_notes_session_fks(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'aud16.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    # Simular tabla legacy conversation_messages y technical_notes sin FK de session_id + huérfanos.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE technical_notes"))
        conn.execute(text("DROP TABLE conversation_messages"))
        conn.execute(
            text(
                """
                CREATE TABLE conversation_messages (
                    id VARCHAR(36) PRIMARY KEY,
                    relationship_id VARCHAR(36) NOT NULL,
                    sender_user_id VARCHAR(36) NOT NULL,
                    sender_role VARCHAR(16) NOT NULL,
                    kind VARCHAR(24) NOT NULL,
                    body TEXT NOT NULL,
                    exercise_id VARCHAR(36),
                    exercise_name VARCHAR(150),
                    session_id VARCHAR(36),
                    set_number INTEGER,
                    reply_to_message_id VARCHAR(36),
                    created_at DATETIME NOT NULL,
                    read_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE technical_notes (
                    id VARCHAR(36) PRIMARY KEY,
                    relationship_id VARCHAR(36) NOT NULL,
                    message_id VARCHAR(36) UNIQUE NOT NULL,
                    exercise_id VARCHAR(36),
                    exercise_name VARCHAR(150) NOT NULL,
                    created_at DATETIME NOT NULL,
                    acknowledged_at DATETIME,
                    acknowledged_session_id VARCHAR(36)
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO conversation_messages VALUES "
                "('m1', 'r1', 'u1', 'STUDENT', 'TECHNICAL_QUERY', 'Hola', NULL, 'Sentadilla', 'orphan-sess', 1, NULL, '2026-11-10 10:00:00', NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO technical_notes VALUES "
                "('n1', 'r1', 'm1', NULL, 'Sentadilla', '2026-11-10 10:00:00', '2026-11-10 10:05:00', 'orphan-sess')"
            )
        )

    apply_migrations(engine)
    insp = inspect(engine)
    cm_fks = {(fk["referred_table"], tuple(fk["constrained_columns"])) for fk in insp.get_foreign_keys("conversation_messages")}
    tn_fks = {(fk["referred_table"], tuple(fk["constrained_columns"])) for fk in insp.get_foreign_keys("technical_notes")}
    assert ("workout_sessions", ("session_id",)) in cm_fks
    assert ("workout_sessions", ("acknowledged_session_id",)) in tn_fks

    with engine.connect() as conn:
        assert conn.execute(text("SELECT session_id FROM conversation_messages WHERE id = 'm1'")).scalar_one() is None
        assert conn.execute(text("SELECT acknowledged_session_id FROM technical_notes WHERE id = 'n1'")).scalar_one() is None


def test_aud20_clean_demo_data_removes_orphan_receipt_files(tmp_path, monkeypatch):
    receipts_dir = tmp_path / "demo_receipts"
    uploads_dir = tmp_path / "demo_uploads"
    receipts_dir.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    non_demo_file = receipts_dir / "non-demo-rel" / "keep.pdf"
    non_demo_file.parent.mkdir(parents=True)
    non_demo_file.write_bytes(PDF_BYTES)

    monkeypatch.setattr("backend.scripts.seed_demo.RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr("backend.scripts.seed_demo.UPLOADS_DIR", uploads_dir)

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        seed_demo_data(db, verbose=False)
        demo_payment = db.scalar(select(InformalPayment))
        assert demo_payment is not None
        demo_receipt = receipts_dir / demo_payment.relationship_id / "recibo.pdf"
        demo_receipt.parent.mkdir(parents=True, exist_ok=True)
        demo_receipt.write_bytes(PDF_BYTES)
        demo_payment.receipt_path = str(demo_receipt)
        db.commit()

        clean_demo_data(db, verbose=False)
        db.commit()
    assert not demo_receipt.exists()
    assert not demo_receipt.parent.exists()
    assert non_demo_file.exists()


def test_aud08_training_evolution_preserves_intermediate_and_same_weight_rep_prs(client):
    api, sessions = client
    trainer = register_and_login(api, "aud08_evo_t@example.com", "TRAINER")
    student = register_and_login(api, "aud08_evo_s@example.com", "STUDENT")
    exercise_id, rel_id, _ = setup_routine_and_assignment(
        api, sessions, trainer, "aud08_evo_s@example.com", trainer_email="aud08_evo_t@example.com"
    )
    with sessions() as db:
        student_id = db.get(TrainingRelationship, rel_id).student_id

    def run(weight: float, reps: str, days_ago: int, finish_session: bool = True) -> tuple[str, dict]:
        s_res = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"})
        assert s_res.status_code == 201
        sid = s_res.json()["id"]
        l_res = api.post(
            f"{ASSIGNED_PATH}/workout-logs",
            headers=student,
            json={
                "exercise_id": exercise_id,
                "day_name": "Día 1",
                "set_number": 1,
                "reps_completed": reps,
                "weight_kg": weight,
                "session_id": sid,
            },
        )
        assert l_res.status_code == 201
        if finish_session:
            assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{sid}/finish", headers=student, json={}).status_code == 200
        with sessions() as db:
            ws = db.get(WorkoutSession, sid)
            ts = _now() - timedelta(days=days_ago)
            ws.started_at = ts
            if finish_session:
                ws.finished_at = ts + timedelta(minutes=30)
            for row in db.scalars(select(WorkoutSetLog).where(WorkoutSetLog.session_id == sid)):
                row.recorded_at = ts + timedelta(minutes=5)
            db.commit()
        return sid, l_res.json()

    from backend.src.models.workout_log import WorkoutSetLog

    # S1: base (50 kg x 8 -> no PR)
    _s1, l1 = run(50.0, "8", days_ago=28)
    assert l1["is_personal_record"] is False

    # S2: PR intermedio por peso (60 kg x 8)
    _s2, l2 = run(60.0, "8", days_ago=21)
    assert l2["is_personal_record"] is True
    assert l2["pr_previous_weight_kg"] == 50.0
    assert l2["pr_previous_reps"] == 8

    # S3: PR por repeticiones con el mismo peso (60 kg x 10)
    s3, l3 = run(60.0, "10", days_ago=14)
    assert l3["is_personal_record"] is True
    assert l3["pr_previous_weight_kg"] == 60.0
    assert l3["pr_previous_reps"] == 8
    s3_summary = api.get(f"{ASSIGNED_PATH}/workout-sessions/{s3}/summary", headers=student).json()
    assert s3_summary["personal_records"][0]["weight_kg"] == 60.0
    assert s3_summary["personal_records"][0]["previous_weight_kg"] == 60.0
    assert s3_summary["personal_records"][0]["previous_reps"] == 8

    # S4: PR posterior por peso (70 kg x 8)
    _s4, l4 = run(70.0, "8", days_ago=7)
    assert l4["is_personal_record"] is True

    # S5: sesión activa sin finalizar con 80 kg -> no contamina ni borra los PRs históricos de evolución.
    _s5, l5 = run(80.0, "8", days_ago=0, finish_session=False)
    assert l5["is_personal_record"] is True

    evo = api.get(f"/api/v1/trainers/me/students/{student_id}/evolution", headers=trainer, params={"group_by": "session"}).json()
    ex_evo = evo["exercises"][0]
    assert [p["is_pr"] for p in ex_evo["points"]] == [False, True, True, True]
    assert ex_evo["last_improvement"]["is_pr"] is True


def test_aud16_check_constraints_for_payments_and_termination_category():
    target_names = {(c.table, c.name) for c in TARGET_CHECK_CONSTRAINTS}
    assert ("informal_payments", "ck_informal_payments_source") in target_names
    assert ("informal_payments", "ck_informal_payments_reject_fields") in target_names
    assert ("training_relationships", "ck_training_relationships_termination_category") in target_names

    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    insp = inspect(eng)
    ip_cks = {c["name"] for c in insp.get_check_constraints("informal_payments")}
    tr_cks = {c["name"] for c in insp.get_check_constraints("training_relationships")}
    assert {"ck_informal_payments_source", "ck_informal_payments_reject_fields"}.issubset(ip_cks)
    assert "ck_training_relationships_termination_category" in tr_cks

    SessionLocal = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    now = _now()
    with SessionLocal() as db:
        db.add_all(
            [
                User(id="u1", email="t@e.com", password_hash="h", role="TRAINER", created_at=now),
                User(id="u2", email="s@e.com", password_hash="h", role="STUDENT", created_at=now),
                TrainerProfile(
                    id="tp1",
                    user_id="u1",
                    full_name="T",
                    bio="B",
                    status="PUBLISHED",
                    created_at=now,
                    updated_at=now,
                    max_students=10,
                ),
                StudentProfile(id="sp1", user_id="u2", first_name="S", last_name="L", created_at=now, updated_at=now),
                TrainingPlan(
                    id="pl1",
                    trainer_id="tp1",
                    title="P",
                    monthly_price=1000,
                    currency="ARS",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                # termination_category=NULL permitido incluso con status='TERMINATED'
                TrainingRelationship(
                    id="rel1",
                    student_id="sp1",
                    trainer_id="tp1",
                    plan_id="pl1",
                    agreed_monthly_price=1000,
                    agreed_currency="ARS",
                    status="TERMINATED",
                    start_date=date(2026, 1, 1),
                    termination_category=None,
                ),
            ]
        )
        db.commit()

    with pytest.raises(IntegrityError), eng.begin() as conn:
        conn.execute(text("INSERT INTO training_relationships (id, student_id, trainer_id, plan_id, agreed_monthly_price, agreed_currency, status, start_date, welcome_message_sent, routine_modality, termination_category) VALUES ('rel2', 'sp1', 'tp1', 'pl1', 1000, 'ARS', 'TERMINATED', '2026-01-01', 1, 'GYM', 'INVALIDA')"))

    with pytest.raises(IntegrityError), eng.begin() as conn:
        conn.execute(text("INSERT INTO informal_payments (id, relationship_id, trainer_id, student_id, paid_on, amount, currency, method, months_covered, status, registered_by_user_id, created_at, source) VALUES ('pay1', 'rel1', 'tp1', 'sp1', '2026-01-01', 1000, 'ARS', 'EFECTIVO', 1, 'CONFIRMADO', 'u1', '2026-01-01', 'OTRO')"))

    with pytest.raises(IntegrityError), eng.begin() as conn:
        conn.execute(text("INSERT INTO informal_payments (id, relationship_id, trainer_id, student_id, paid_on, amount, currency, method, months_covered, status, registered_by_user_id, created_at, source, rejection_reason) VALUES ('pay2', 'rel1', 'tp1', 'sp1', '2026-01-01', 1000, 'ARS', 'EFECTIVO', 1, 'RECHAZADO', 'u1', '2026-01-01', 'STUDENT', NULL)"))
