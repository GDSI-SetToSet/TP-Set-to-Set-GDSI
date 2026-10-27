import io
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import jwt
import pytest
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.src.core.config import JWT_ALGORITHM, JWT_SECRET
from backend.src.core.database import Base
from backend.src.core.security import (
    create_session_credentials,
    decode_access_token,
    hash_password,
)
from backend.src.core.storage import StorageError, open_upload, sanitize_filename
from backend.src.models import (
    HealthQuestionnaire,
    MedicalClearance,
    Notification,
    StudentProfile,
    TrainerProfile,
    TrainingPlan,
    TrainingRelationship,
    TrainingRequest,
    User,
    UserSession,
)
from backend.src.schemas.discovery import TrainingRequestCreate
from backend.src.services.discovery_service import (
    DiscoveryError,
    create_training_request,
)

TRAINER_PUBLISHED_PAYLOAD = {
    "full_name": "Coach Adversarial",
    "contact_phone": "+5491155551234",
    "specialty": "Fuerza",
}

STUDENT_PROFILE_PAYLOAD = {
    "first_name": "Lucía",
    "last_name": "Privacidad",
    "birth_date": "1996-04-15T00:00:00Z",
    "contact_phone": "+5491144445555",
    "fitness_goals": ["fuerza", "salud_general"],
    "personal_motivation": "Mejorar postura y fuerza general",
}

HEALTH_QUESTIONNAIRE_PAYLOAD = {
    "has_heart_condition": False,
    "has_chest_pain_activity": False,
    "has_dizziness_or_balance_loss": False,
    "has_bone_joint_problem": True,
    "takes_prescription_meds": False,
    "other_medical_conditions": "Esguince de tobillo previo",
}


def _register_and_login(test_client, email: str, role: str, password: str = "StrongPass123"):
    reg = test_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "role": role},
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["id"]
    login = test_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user_id, token, {"Authorization": f"Bearer {token}"}


def _setup_published_trainer(test_client, headers: dict, max_students: int = 5) -> tuple[str, str]:
    prof = test_client.put(
        "/api/v1/trainers/me/profile",
        json=TRAINER_PUBLISHED_PAYLOAD,
        headers=headers,
    )
    assert prof.status_code == 200, prof.text
    trainer_profile_id = prof.json()["id"]

    quota = test_client.patch(
        "/api/v1/trainers/me/quota",
        json={"max_students": max_students},
        headers=headers,
    )
    assert quota.status_code == 200, quota.text

    plan = test_client.post(
        "/api/v1/trainers/me/plans",
        json={"title": "Plan Fuerza Elite", "monthly_price": 25000},
        headers=headers,
    )
    assert plan.status_code == 201, plan.text
    return trainer_profile_id, plan.json()["id"]


def _setup_complete_student(test_client, headers: dict) -> str:
    prof = test_client.put(
        "/api/v1/students/me/profile",
        json=STUDENT_PROFILE_PAYLOAD,
        headers=headers,
    )
    assert prof.status_code == 200, prof.text
    student_profile_id = prof.json()["id"]

    hq = test_client.post(
        "/api/v1/students/me/health-questionnaire",
        json=HEALTH_QUESTIONNAIRE_PAYLOAD,
        headers=headers,
    )
    assert hq.status_code == 201, hq.text
    return student_profile_id


# ============================================================================
# FASE 1 — H-01: Concurrencia real, índice único parcial y manejo de IntegrityError
# ============================================================================


def test_h01_partial_unique_index_exists_in_sqlite_schema(client):
    _, session_local = client
    with session_local() as db:
        row = db.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name='training_requests' "
                "AND name='uq_pending_training_request'"
            )
        ).fetchone()
        assert row is not None
        assert "UNIQUE INDEX uq_pending_training_request" in row[0]
        assert "WHERE status = 'PENDING'" in row[0]


def test_h01_concurrent_threads_on_file_sqlite_enforce_single_pending_request(tmp_path):
    db_file = tmp_path / "h01_concurrent.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    try:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            student_user = User(
                email="concurrent_student@example.com",
                password_hash=hash_password("StrongPass123"),
                role="STUDENT",
                created_at=now,
            )
            trainer_user = User(
                email="concurrent_trainer@example.com",
                password_hash=hash_password("StrongPass123"),
                role="TRAINER",
                created_at=now,
            )
            db.add_all([student_user, trainer_user])
            db.flush()

            student_prof = StudentProfile(
                user_id=student_user.id,
                first_name="Ana",
                last_name="Concurrente",
                birth_date=now - timedelta(days=365 * 25),
                contact_phone="+5491100001111",
                fitness_goals=["fuerza"],
                status="PUBLISHED",
                created_at=now,
                updated_at=now,
            )
            trainer_prof = TrainerProfile(
                user_id=trainer_user.id,
                full_name="Trainer Concurrente",
                contact_phone="+5491155551234",
                specialty="Fuerza",
                status="PUBLISHED",
                max_students=5,
                created_at=now,
                updated_at=now,
            )
            db.add_all([student_prof, trainer_prof])
            db.flush()

            hq = HealthQuestionnaire(
                student_id=student_prof.id,
                has_heart_condition=False,
                has_chest_pain_activity=False,
                has_dizziness_or_balance_loss=False,
                has_bone_joint_problem=False,
                takes_prescription_meds=False,
                other_medical_conditions=None,
                status="CURRENT",
                completed_at=now,
            )
            plan = TrainingPlan(
                trainer_id=trainer_prof.id,
                title="Plan Base",
                monthly_price=Decimal("15000.00"),
                currency="ARS",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add_all([hq, plan])
            db.commit()

            student_user_id = student_user.id
            student_prof_id = student_prof.id
            trainer_user_id = trainer_user.id
            trainer_prof_id = trainer_prof.id
            plan_id = plan.id

        workers = 6
        barrier = threading.Barrier(workers)

        def _worker(idx: int):
            with SessionLocal() as thread_db:
                s_user = thread_db.get(User, student_user_id)
                barrier.wait(timeout=5)
                try:
                    req = create_training_request(
                        thread_db,
                        s_user,
                        TrainingRequestCreate(
                            trainer_id=trainer_prof_id,
                            plan_id=plan_id,
                            student_message=f"Intento concurrente {idx}",
                        ),
                    )
                    return ("OK", req.id)
                except DiscoveryError as exc:
                    return ("DISCOVERY_ERROR", exc.status_code)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_worker, range(workers)))

        successes = [r for r in results if r[0] == "OK"]
        conflicts = [r for r in results if r == ("DISCOVERY_ERROR", 409)]
        assert len(successes) == 1
        assert len(conflicts) == workers - 1

        with SessionLocal() as db:
            pending_rows = (
                db.query(TrainingRequest)
                .filter(
                    TrainingRequest.student_id == student_prof_id,
                    TrainingRequest.trainer_id == trainer_prof_id,
                    TrainingRequest.status == "PENDING",
                )
                .all()
            )
            assert len(pending_rows) == 1
            # Transactional coherence: exactly 1 NEW_REQUEST notification persisted (no orphans)
            trainer_notifs = (
                db.query(Notification)
                .filter(Notification.recipient_id == trainer_user_id)
                .all()
            )
            assert len(trainer_notifs) == 1
            assert trainer_notifs[0].type == "NEW_REQUEST"
            assert trainer_notifs[0].related_entity_id == pending_rows[0].id
    finally:
        engine.dispose()


def test_h01_unrelated_integrity_error_is_reraised_not_masked_as_409(client, monkeypatch):
    test_client, session_local = client
    _, _, student_headers = _register_and_login(test_client, "s_unrel@example.com", "STUDENT")
    _, _, trainer_headers = _register_and_login(test_client, "t_unrel@example.com", "TRAINER")
    trainer_prof_id, plan_id = _setup_published_trainer(test_client, trainer_headers)
    _setup_complete_student(test_client, student_headers)

    with session_local() as db:
        student = db.query(User).filter(User.email == "s_unrel@example.com").one()

        def _raise_unrelated_integrity_error():
            raise IntegrityError(
                "INSERT INTO notifications ...",
                params={},
                orig=Exception("FOREIGN KEY constraint failed"),
            )

        monkeypatch.setattr(db, "commit", _raise_unrelated_integrity_error)
        with pytest.raises(IntegrityError):
            create_training_request(
                db,
                student,
                TrainingRequestCreate(
                    trainer_id=trainer_prof_id,
                    plan_id=plan_id,
                    student_message="Deberia relanzar IntegrityError no relacionado",
                ),
            )

    # Verificación observable post-rollback en sesión nueva: 0 registros persistidos
    with session_local() as db_fresh:
        assert db_fresh.scalar(select(func.count(TrainingRequest.id))) == 0
        assert db_fresh.scalar(select(func.count(Notification.id))) == 0


def test_h01_observable_rollback_after_flush_on_notification_failure_and_retry(client, monkeypatch):
    """M-01: Provoca una excepción no relacionada con duplicados después de que la solicitud
    ha sido incorporada (db.add) y flusheada (db.flush) en create_training_request.
    Verifica mediante una sesión nueva que:
    1. No existe la solicitud creada por la operación fallida.
    2. No existe la notificación asociada.
    3. La excepción original se propaga correctamente.
    4. Los errores ajenos a duplicados no se convierten en HTTP 409.
    5. La operación posterior puede completarse exitosamente sin bloqueos ni conflictos residuales.
    """
    test_client, session_local = client
    _, _, student_headers = _register_and_login(test_client, "s_rollback@example.com", "STUDENT")
    _, _, trainer_headers = _register_and_login(test_client, "t_rollback@example.com", "TRAINER")
    trainer_prof_id, plan_id = _setup_published_trainer(test_client, trainer_headers)
    _setup_complete_student(test_client, student_headers)

    captured_request_id = None

    def _failing_create_notification(**kwargs):
        nonlocal captured_request_id
        # La solicitud ya fue incorporada y flusheada, por lo que tiene un ID asignado en la transacción
        captured_request_id = kwargs.get("related_entity_id")
        assert captured_request_id is not None
        raise RuntimeError("Fallo simulado tras db.flush en create_notification")

    with session_local() as db:
        student = db.query(User).filter(User.email == "s_rollback@example.com").one()
        monkeypatch.setattr(
            "backend.src.services.discovery_service.create_notification",
            _failing_create_notification,
        )

        with pytest.raises(RuntimeError, match="Fallo simulado tras db.flush"):
            create_training_request(
                db,
                student,
                TrainingRequestCreate(
                    trainer_id=trainer_prof_id,
                    plan_id=plan_id,
                    student_message="Mensaje que sufrira rollback",
                ),
            )

    assert captured_request_id is not None

    # Verificación observable con una sesión nueva de base de datos
    with session_local() as db_fresh:
        assert db_fresh.get(TrainingRequest, captured_request_id) is None
        assert db_fresh.scalar(select(func.count(TrainingRequest.id))) == 0
        assert db_fresh.scalar(select(func.count(Notification.id))) == 0

    # Verificación en endpoint API: un fallo no relacionado produce error de servidor y no 409 Conflict
    monkeypatch.setattr(
        "backend.src.services.discovery_service.create_notification",
        _failing_create_notification,
    )
    with test_client.__class__(test_client.app, raise_server_exceptions=False) as no_raise_client:
        api_resp = no_raise_client.post(
            "/api/v1/matchmaking/requests",
            headers=student_headers,
            json={"trainer_id": trainer_prof_id, "plan_id": plan_id},
        )
        assert api_resp.status_code == 500
        assert api_resp.status_code != 409

    with session_local() as db_fresh:
        assert db_fresh.scalar(select(func.count(TrainingRequest.id))) == 0
        assert db_fresh.scalar(select(func.count(Notification.id))) == 0

    # Reintento exitoso una vez removida la falla inyectada
    monkeypatch.undo()
    retry_resp = test_client.post(
        "/api/v1/matchmaking/requests",
        headers=student_headers,
        json={"trainer_id": trainer_prof_id, "plan_id": plan_id, "student_message": "Reintento exitoso"},
    )
    assert retry_resp.status_code == 201
    created_id = retry_resp.json()["id"]

    with session_local() as db_fresh:
        req = db_fresh.get(TrainingRequest, created_id)
        assert req is not None
        assert req.status == "PENDING"
        notif = db_fresh.scalar(select(Notification).where(Notification.related_entity_id == created_id))
        assert notif is not None
        assert notif.type == "NEW_REQUEST"


# ============================================================================
# FASE 2 — H-02: Matriz adversarial de autorización en Notificaciones (US-49)
# ============================================================================


def test_h02_notification_rbac_cross_student_trainer_and_session_states(client):
    test_client, session_local = client
    s1_id, _, s1_headers = _register_and_login(test_client, "s1_notif@example.com", "STUDENT")
    _, _, s2_headers = _register_and_login(test_client, "s2_notif@example.com", "STUDENT")
    t1_id, _, t1_headers = _register_and_login(test_client, "t1_notif@example.com", "TRAINER")
    _, _, t2_headers = _register_and_login(test_client, "t2_notif@example.com", "TRAINER")

    with session_local() as db:
        notif = Notification(
            recipient_id=s1_id,
            type="TRAINING_ACCEPTED",
            title="Bienvenida",
            message="Mensaje para alumna 1",
            is_read=False,
            created_at=datetime.now(UTC),
        )
        trainer_notif = Notification(
            recipient_id=t1_id,
            type="NEW_REQUEST",
            title="¡Nueva solicitud de entrenamiento!",
            message="Mensaje para entrenador 1",
            is_read=False,
            created_at=datetime.now(UTC),
        )
        db.add_all([notif, trainer_notif])
        db.commit()
        notif_id = notif.id
        trainer_notif_id = trainer_notif.id

    # 1. Otro alumno no puede marcar la notificación de s1 y no altera is_read
    res_other_student = test_client.patch(
        f"/api/v1/students/me/notifications/{notif_id}/read",
        headers=s2_headers,
    )
    assert res_other_student.status_code == 403

    # 2. Entrenador no puede listar ni marcar en endpoints de alumno
    res_trainer_list = test_client.get("/api/v1/students/me/notifications", headers=t1_headers)
    assert res_trainer_list.status_code == 403

    res_trainer_mark = test_client.patch(
        f"/api/v1/students/me/notifications/{notif_id}/read",
        headers=t1_headers,
    )
    assert res_trainer_mark.status_code == 403

    # 2b. Alumna no puede listar ni marcar en endpoints de entrenador, y otro entrenador tampoco puede marcar la de t1
    assert test_client.get("/api/v1/trainers/me/notifications", headers=s1_headers).status_code == 403
    assert (
        test_client.patch(
            f"/api/v1/trainers/me/notifications/{trainer_notif_id}/read",
            headers=s1_headers,
        ).status_code
        == 403
    )
    assert (
        test_client.patch(
            f"/api/v1/trainers/me/notifications/{trainer_notif_id}/read",
            headers=t2_headers,
        ).status_code
        == 403
    )

    # Verificar que en la base siguen is_read == False tras todos los intentos denegados
    with session_local() as db:
        persisted = db.get(Notification, notif_id)
        assert persisted.is_read is False
        persisted_trainer = db.get(Notification, trainer_notif_id)
        assert persisted_trainer.is_read is False

    # 3. Parámetros límite inválidos en listado
    assert test_client.get("/api/v1/students/me/notifications?limit=0", headers=s1_headers).status_code == 422
    assert test_client.get("/api/v1/students/me/notifications?limit=101", headers=s1_headers).status_code == 422
    assert test_client.get("/api/v1/students/me/notifications?offset=-1", headers=s1_headers).status_code == 422
    assert test_client.get("/api/v1/trainers/me/notifications?limit=0", headers=t1_headers).status_code == 422

    # 4. Notificación inexistente
    assert (
        test_client.patch(
            "/api/v1/students/me/notifications/00000000-0000-0000-0000-000000000000/read",
            headers=s1_headers,
        ).status_code
        == 404
    )
    assert (
        test_client.patch(
            "/api/v1/trainers/me/notifications/00000000-0000-0000-0000-000000000000/read",
            headers=t1_headers,
        ).status_code
        == 404
    )

    # 5. Propietarios (alumna y entrenador) pueden listar y marcar como leída en su propio endpoint
    res_own_mark = test_client.patch(
        f"/api/v1/students/me/notifications/{notif_id}/read",
        headers=s1_headers,
    )
    assert res_own_mark.status_code == 200
    assert res_own_mark.json()["is_read"] is True

    res_trainer_own_list = test_client.get("/api/v1/trainers/me/notifications", headers=t1_headers)
    assert res_trainer_own_list.status_code == 200
    assert res_trainer_own_list.json()["total"] == 1
    res_trainer_own_mark = test_client.patch(
        f"/api/v1/trainers/me/notifications/{trainer_notif_id}/read",
        headers=t1_headers,
    )
    assert res_trainer_own_mark.status_code == 200
    assert res_trainer_own_mark.json()["is_read"] is True

    # 6. Usuario deshabilitado (is_active=False) es rechazado con 401
    with session_local() as db:
        s1_user = db.get(User, s1_id)
        s1_user.is_active = False
        db.commit()

    res_disabled = test_client.get("/api/v1/students/me/notifications", headers=s1_headers)
    assert res_disabled.status_code == 401


# ============================================================================
# FASE 3 — H-03: Privacidad y exposición de PII en todos los estados de vínculo
# ============================================================================


def test_h03_pii_and_health_access_across_all_request_and_relationship_transitions(client):
    test_client, session_local = client
    _, _, s_headers = _register_and_login(test_client, "s_pii@example.com", "STUDENT")
    _, _, t1_headers = _register_and_login(test_client, "t1_pii@example.com", "TRAINER")
    _, _, t2_headers = _register_and_login(test_client, "t2_pii@example.com", "TRAINER")

    t1_prof_id, plan1_id = _setup_published_trainer(test_client, t1_headers)
    _setup_published_trainer(test_client, t2_headers)
    s_prof_id = _setup_complete_student(test_client, s_headers)

    # Crear solicitud PENDING
    req_resp = test_client.post(
        "/api/v1/matchmaking/requests",
        json={"trainer_id": t1_prof_id, "plan_id": plan1_id, "student_message": "Hola"},
        headers=s_headers,
    )
    assert req_resp.status_code == 201, req_resp.text
    req1_id = req_resp.json()["id"]

    # En PENDING, /api/v1/students/me/active-plans NO debe exponer email ni teléfono privado del entrenador
    student_plans_pending = test_client.get(
        "/api/v1/students/me/active-plans", headers=s_headers
    )
    assert student_plans_pending.status_code == 200
    pending_items = student_plans_pending.json()
    assert len(pending_items) == 1
    assert pending_items[0]["status"] == "PENDING"
    assert pending_items[0]["has_active_plan"] is False
    assert pending_items[0]["trainer"]["email"] is None
    assert pending_items[0]["trainer"]["phone"] is None

    # Estado 1: PENDING -> entrenador destino ve PII; otro entrenador y alumna reciben 403
    det_pending = test_client.get(f"/api/v1/matchmaking/requests/{req1_id}", headers=t1_headers)
    assert det_pending.status_code == 200
    assert det_pending.json()["student"]["contact_phone"] == "+5491144445555"
    assert det_pending.json()["student"]["birth_date"].startswith("1996-04-15")

    assert test_client.get(f"/api/v1/matchmaking/requests/{req1_id}", headers=t2_headers).status_code == 403
    assert test_client.get(f"/api/v1/matchmaking/requests/{req1_id}", headers=s_headers).status_code == 403
    assert test_client.get("/api/v1/matchmaking/requests/nonexistent-id", headers=t1_headers).status_code == 404

    # Estado 2: CANCELLED sin vínculo activo -> PII redactado y endpoints de salud devuelven 403
    with session_local() as db:
        r1 = db.get(TrainingRequest, req1_id)
        r1.status = "CANCELLED"
        db.commit()

    det_cancelled = test_client.get(f"/api/v1/matchmaking/requests/{req1_id}", headers=t1_headers)
    assert det_cancelled.status_code == 200
    assert det_cancelled.json()["student"]["contact_phone"] is None
    assert det_cancelled.json()["student"]["birth_date"] is None
    assert test_client.get(f"/api/v1/students/{s_prof_id}/goals", headers=t1_headers).status_code == 403
    assert test_client.get(f"/api/v1/students/{s_prof_id}/health-questionnaire", headers=t1_headers).status_code == 403

    # Estado 3: Nueva solicitud PENDING re-habilita acceso tras estado inactivo
    req2_resp = test_client.post(
        "/api/v1/matchmaking/requests",
        json={"trainer_id": t1_prof_id, "plan_id": plan1_id, "student_message": "Vuelvo a intentar"},
        headers=s_headers,
    )
    assert req2_resp.status_code == 201, req2_resp.text
    req2_id = req2_resp.json()["id"]
    det_reopened = test_client.get(f"/api/v1/matchmaking/requests/{req2_id}", headers=t1_headers)
    assert det_reopened.status_code == 200
    assert det_reopened.json()["student"]["contact_phone"] == "+5491144445555"
    assert test_client.get(f"/api/v1/students/{s_prof_id}/goals", headers=t1_headers).status_code == 200

    # Estado 4: ACCEPTED con relación ACTIVE -> PII visible para entrenador y contacto del entrenador visible para alumna
    acc_resp = test_client.post(
        f"/api/v1/matchmaking/requests/{req2_id}/accept",
        json={"welcome_message": "Bienvenida al equipo"},
        headers=t1_headers,
    )
    assert acc_resp.status_code == 200, acc_resp.text
    det_accepted = test_client.get(f"/api/v1/matchmaking/requests/{req2_id}", headers=t1_headers)
    assert det_accepted.status_code == 200
    assert det_accepted.json()["student"]["contact_phone"] == "+5491144445555"

    student_plans_active = test_client.get(
        "/api/v1/students/me/active-plans", headers=s_headers
    ).json()
    assert len(student_plans_active) == 1
    assert student_plans_active[0]["status"] == "ACTIVE"
    assert student_plans_active[0]["has_active_plan"] is True
    assert student_plans_active[0]["trainer"]["email"] == "t1_pii@example.com"
    assert student_plans_active[0]["trainer"]["phone"] == "+5491155551234"

    # Estado 5: La relación pasa a TERMINATED o EXPIRED -> se revoca el acceso a PII y salud en solicitudes históricas ACCEPTED
    for inactive_rel_status in ("TERMINATED", "EXPIRED"):
        with session_local() as db:
            rel = (
                db.query(TrainingRelationship)
                .filter(
                    TrainingRelationship.student_id == s_prof_id,
                    TrainingRelationship.trainer_id == t1_prof_id,
                )
                .one()
            )
            rel.status = inactive_rel_status
            db.commit()

        det_after_end = test_client.get(f"/api/v1/matchmaking/requests/{req2_id}", headers=t1_headers)
        assert det_after_end.status_code == 200
        assert det_after_end.json()["student"]["contact_phone"] is None
        assert det_after_end.json()["student"]["birth_date"] is None
        assert test_client.get(f"/api/v1/students/{s_prof_id}/goals", headers=t1_headers).status_code == 403
        assert test_client.get(f"/api/v1/students/{s_prof_id}/health-questionnaire", headers=t1_headers).status_code == 403
        assert test_client.get("/api/v1/students/me/active-plans", headers=s_headers).json() == []


# ============================================================================
# FASE 4 — H-04: Escalabilidad O(1) queries (sin N+1) y escape de wildcards LIKE
# ============================================================================


def test_h04_search_trainers_query_count_remains_constant_for_10_50_and_150_trainers(client):
    test_client, session_local = client
    _, _, student_headers = _register_and_login(test_client, "s_perf@example.com", "STUDENT")

    with session_local() as db:
        engine = db.get_bind()

    def _seed_trainers(target_total: int, current_total: int):
        now = datetime.now(UTC)
        with session_local() as db:
            for idx in range(current_total, target_total):
                u = User(
                    email=f"trainer_scale_{idx}@example.com",
                    password_hash="hashed",
                    role="TRAINER",
                    created_at=now,
                )
                db.add(u)
                db.flush()
                prof = TrainerProfile(
                    user_id=u.id,
                    full_name=f"Entrenador Escala {idx:03d}",
                    contact_phone="+5491155550000",
                    specialty="Fuerza" if idx % 2 == 0 else "Yoga",
                    status="PUBLISHED",
                    max_students=3,
                    created_at=now,
                    updated_at=now,
                )
                db.add(prof)
                db.flush()
                plan = TrainingPlan(
                    trainer_id=prof.id,
                    title=f"Plan {idx}",
                    monthly_price=Decimal(str(15000 + (idx * 100))),
                    currency="ARS",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(plan)
            db.commit()

    def _measure_queries(url: str) -> tuple[int, dict]:
        statements: list[str] = []

        def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _before_cursor_execute)
        try:
            resp = test_client.get(url, headers=student_headers)
            assert resp.status_code == 200, resp.text
            return len(statements), resp.json()
        finally:
            event.remove(engine, "before_cursor_execute", _before_cursor_execute)

    _seed_trainers(10, 0)
    q_10, body_10 = _measure_queries("/api/v1/trainers/search?only_available=true&page=1&page_size=20")
    assert body_10["total"] == 10

    _seed_trainers(50, 10)
    q_50, body_50 = _measure_queries("/api/v1/trainers/search?only_available=true&page=1&page_size=20")
    assert body_50["total"] == 50

    _seed_trainers(150, 50)
    q_150, body_150 = _measure_queries("/api/v1/trainers/search?only_available=true&page=1&page_size=20")
    assert body_150["total"] == 150

    # Número de consultas SQL estrictamente constante (sin N+1)
    assert q_10 == q_50 == q_150
    assert q_150 <= 4


def test_h04_search_trainers_wildcard_injection_and_negative_price_validation(client):
    test_client, _ = client
    _, _, student_headers = _register_and_login(test_client, "s_wild@example.com", "STUDENT")
    _, _, trainer_headers = _register_and_login(test_client, "t_wild@example.com", "TRAINER")
    _setup_published_trainer(test_client, trainer_headers)

    # "%" y "_" no deben actuar como comodines SQL LIKE
    res_percent = test_client.get("/api/v1/trainers/search?specialty=%25", headers=student_headers)
    assert res_percent.status_code == 200
    assert res_percent.json()["total"] == 0

    res_underscore = test_client.get("/api/v1/trainers/search?specialty=_", headers=student_headers)
    assert res_underscore.status_code == 200
    assert res_underscore.json()["total"] == 0

    # max_price negativo y paginación fuera de rango deben rechazarse con 422
    assert test_client.get("/api/v1/trainers/search?max_price=-1", headers=student_headers).status_code == 422
    assert test_client.get("/api/v1/trainers/search?page=0", headers=student_headers).status_code == 422
    assert test_client.get("/api/v1/trainers/search?page_size=51", headers=student_headers).status_code == 422


# ============================================================================
# FASE 5 — H-05 (8.1 & 8.2): Hardening de JWT/Sesiones y Archivos/Symlinks
# ============================================================================


def test_h05_jwt_claim_manipulation_and_session_lifecycle_across_endpoints(client):
    test_client, session_local = client
    user_id, valid_token, valid_headers = _register_and_login(
        test_client, "s_jwt@example.com", "STUDENT"
    )
    decoded = decode_access_token(valid_token)
    valid_jti = decoded["jti"]

    protected_endpoints = [
        "/api/v1/auth/me",
        "/api/v1/trainers/search",
        "/api/v1/students/me/profile",
        "/api/v1/students/me/notifications",
    ]

    # 1. JWT firmado con la clave correcta pero SIN claim "exp" -> rechazado
    token_no_exp = jwt.encode(
        {"sub": user_id, "jti": valid_jti, "role": "STUDENT"},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    # 2. JWT con tipos no string en sub / jti -> rechazado con 401 (nunca 500)
    token_bad_types = jwt.encode(
        {
            "sub": 12345,
            "jti": ["array_jti"],
            "role": "STUDENT",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    # 3. JWT con firma válida pero jti inexistente en DB -> rechazado con 401
    token_ghost_jti, _, _ = create_session_credentials(
        user_id=user_id, role="STUDENT", now=datetime.now(UTC)
    )

    for ep in protected_endpoints:
        assert test_client.get(ep, headers=valid_headers).status_code == 200
        assert (
            test_client.get(ep, headers={"Authorization": f"Bearer {token_no_exp}"}).status_code
            == 401
        )
        assert (
            test_client.get(ep, headers={"Authorization": f"Bearer {token_bad_types}"}).status_code
            == 401
        )
        assert (
            test_client.get(ep, headers={"Authorization": f"Bearer {token_ghost_jti}"}).status_code
            == 401
        )

    # 4. Sesión expirada en base de datos (aunque el JWT aún no haya expirado) -> 401
    with session_local() as db:
        sess = db.query(UserSession).filter(UserSession.jti == valid_jti).one()
        sess.expires_at = datetime.now(UTC) - timedelta(seconds=10)
        db.commit()

    for ep in protected_endpoints:
        assert test_client.get(ep, headers=valid_headers).status_code == 401


def test_h05_filename_sanitization_windows_reserved_chars_and_symlink_protection(client, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.src.core.storage.UPLOADS_DIR", tmp_path / "uploads")
    test_client, session_local = client
    _, _, s_headers = _register_and_login(test_client, "s_files@example.com", "STUDENT")
    s_prof_id = _setup_complete_student(test_client, s_headers)

    # 1. Nombres maliciosos, caracteres ilegales en Windows/NTFS, Bidi override y dispositivos reservados
    assert sanitize_filename("C:..\\..\\Windows\\System32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("apto<>:\"|?*.pdf") == "apto.pdf"
    assert sanitize_filename("CON.pdf") == "apto.pdf"
    assert sanitize_filename("aux.png") == "apto.png"
    assert sanitize_filename("report\u202efdp.exe") == "reportfdp.exe"
    long_name = ("a" * 260) + ".pdf"
    sanitized_long = sanitize_filename(long_name)
    assert len(sanitized_long) == 200
    assert sanitized_long.endswith(".pdf")

    # 2. Subida multipart con caracteres ilegales en Windows/NTFS no debe causar 500 OSError
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    up1 = test_client.post(
        "/api/v1/students/me/medical-clearance",
        data={"issue_date": "2026-01-10"},
        files={"file": ("apto<>:|?*.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=s_headers,
    )
    assert up1.status_code == 201, up1.text
    assert up1.json()["original_filename"] == "apto.pdf"

    # 3. Dos cargas con el mismo nombre generan rutas físicas distintas (UUIDv4)
    up2 = test_client.post(
        "/api/v1/students/me/medical-clearance",
        data={"issue_date": "2026-01-15"},
        files={"file": ("apto<>:|?*.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=s_headers,
    )
    assert up2.status_code == 201, up2.text

    with session_local() as db:
        rows = (
            db.query(MedicalClearance)
            .filter(MedicalClearance.student_id == s_prof_id)
            .all()
        )
        assert len(rows) == 2
        assert rows[0].file_path != rows[1].file_path
        current_rows = [r for r in rows if r.status == "CURRENT"]
        assert len(current_rows) == 1
        current_id = current_rows[0].id

    # 4. Protección contra symlinks y archivos señuelo fuera de UPLOADS_DIR
    decoy_file = tmp_path / "secret_decoy.pdf"
    decoy_file.write_bytes(b"TOP_SECRET_DECOY")

    symlink_inside = (tmp_path / "uploads") / "symlink_to_secret.pdf"
    symlink_created = False
    try:
        symlink_inside.symlink_to(decoy_file)
        symlink_created = True
    except OSError:
        symlink_created = False

    if symlink_created:
        with pytest.raises(StorageError):
            open_upload(str(symlink_inside))

    # Intentar apuntar file_path en DB al archivo señuelo fuera de UPLOADS_DIR
    with session_local() as db:
        mc = db.get(MedicalClearance, current_id)
        mc.file_path = str(decoy_file)
        db.commit()

    dl_resp = test_client.get(
        f"/api/v1/students/{s_prof_id}/medical-clearance/download", headers=s_headers
    )
    assert dl_resp.status_code == 404
    assert decoy_file.read_bytes() == b"TOP_SECRET_DECOY"


# ============================================================================
# FASE 6 & 7 — H-06 (Contratos) y Defectos adicionales (A-07, A-08)
# ============================================================================


def test_a07_medical_clearance_partial_unique_index_and_orphan_file_cleanup(client, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.src.core.storage.UPLOADS_DIR", tmp_path / "uploads_a07")
    test_client, session_local = client
    _, _, s_headers = _register_and_login(test_client, "s_a07@example.com", "STUDENT")
    s_prof_id = _setup_complete_student(test_client, s_headers)

    # 1. Verificar que el índice parcial único existe en SQLite
    now = datetime.now(UTC)
    with session_local() as db:
        row = db.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name='medical_clearances' "
                "AND name='uq_medical_clearances_current'"
            )
        ).fetchone()
        assert row is not None
        assert "WHERE status = 'CURRENT'" in row[0]

        # Insertar dos registros CURRENT para el mismo alumno debe fallar por IntegrityError
        mc1 = MedicalClearance(
            student_id=s_prof_id,
            file_path="p1.pdf",
            original_filename="p1.pdf",
            mime_type="application/pdf",
            file_size_bytes=100,
            issue_date=date(2026, 1, 1),
            status="CURRENT",
            created_at=now,
        )
        mc2 = MedicalClearance(
            student_id=s_prof_id,
            file_path="p2.pdf",
            original_filename="p2.pdf",
            mime_type="application/pdf",
            file_size_bytes=100,
            issue_date=date(2026, 1, 2),
            status="CURRENT",
            created_at=now,
        )
        db.add_all([mc1, mc2])
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    # 2. Si falla db.commit() durante upload_medical_clearance, el archivo físico se limpia (sin huérfanos)
    import asyncio

    from fastapi import UploadFile

    from backend.src.services.student_service import upload_medical_clearance

    with session_local() as db:
        user = db.query(User).filter(User.email == "s_a07@example.com").one()

        def _fail_commit():
            raise RuntimeError("Simulated DB commit crash")

        monkeypatch.setattr(db, "commit", _fail_commit)

        upload_obj = UploadFile(
            filename="orphan.pdf",
            file=io.BytesIO(b"%PDF-1.4\norphan test"),
            headers={"content-type": "application/pdf"},
        )
        with pytest.raises(RuntimeError, match="Simulated DB commit crash"):
            asyncio.run(upload_medical_clearance(db, user, upload_obj, date(2026, 2, 1)))

    uploads_dir = tmp_path / "uploads_a07"
    remaining_files = list(uploads_dir.rglob("*")) if uploads_dir.exists() else []
    assert [f for f in remaining_files if f.is_file()] == []


def test_a08_student_profile_rejects_whitespace_only_names_for_publication(client):
    test_client, _ = client
    _, _, s_headers = _register_and_login(test_client, "s_a08@example.com", "STUDENT")

    # 1. Perfil en DRAFT con espacios en blanco en first_name y last_name NO pasa a PUBLISHED
    resp_draft = test_client.put(
        "/api/v1/students/me/profile",
        json={
            **STUDENT_PROFILE_PAYLOAD,
            "first_name": "    ",
            "last_name": "   \t  ",
        },
        headers=s_headers,
    )
    assert resp_draft.status_code == 200
    assert resp_draft.json()["first_name"] is None
    assert resp_draft.json()["last_name"] is None
    assert resp_draft.json()["status"] == "DRAFT"

    # 2. Publicar perfil con nombres reales -> pasa a PUBLISHED
    resp_pub = test_client.put(
        "/api/v1/students/me/profile",
        json=STUDENT_PROFILE_PAYLOAD,
        headers=s_headers,
    )
    assert resp_pub.status_code == 200
    assert resp_pub.json()["status"] == "PUBLISHED"

    # 3. Intentar sobreescribir first_name con solo espacios en un perfil PUBLISHED -> 422
    resp_blank_pub = test_client.put(
        "/api/v1/students/me/profile",
        json={"first_name": "     "},
        headers=s_headers,
    )
    assert resp_blank_pub.status_code == 422


def test_h06_openapi_yaml_contracts_and_readme_routes_match_implementation(client):
    test_client, _ = client

    # 1. Extraer rutas registradas en FastAPI mediante /openapi.json
    openapi_resp = test_client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    openapi_paths = openapi_resp.json()["paths"]
    registered_routes: dict[str, set[str]] = {
        path: {m.upper() for m in methods_dict}
        for path, methods_dict in openapi_paths.items()
    }

    # 2. Verificar los 4 contratos OpenAPI de los Sprints 1 y 2 (001 a 004)
    repo_root = Path(__file__).resolve().parents[2]
    contract_files = sorted(
        p
        for p in (repo_root / "taskify" / "specs").glob("00[1-4]-*/contracts/*.yaml")
    )
    assert len(contract_files) == 4

    path_pattern = re.compile(r"^  (/api/v1/[^:]+):\s*$")
    method_pattern = re.compile(r"^    (get|post|put|patch|delete):\s*$")

    for yaml_file in contract_files:
        current_path = None
        for raw_line in yaml_file.read_text(encoding="utf-8").splitlines():
            m_path = path_pattern.match(raw_line)
            if m_path:
                current_path = m_path.group(1)
                assert current_path in registered_routes, (
                    f"Ruta {current_path} en {yaml_file.name} no existe en FastAPI"
                )
                continue
            m_method = method_pattern.match(raw_line)
            if m_method and current_path:
                http_method = m_method.group(1).upper()
                assert http_method in registered_routes[current_path], (
                    f"Método {http_method} {current_path} en {yaml_file.name} no coincide con FastAPI"
                )

    # 3. Verificar en matchmaking-api.yaml los campos request_id, requested_at, PENDING y NEW_REQUEST
    matchmaking_yaml = (
        repo_root
        / "taskify"
        / "specs"
        / "004-discovery-and-matchmaking"
        / "contracts"
        / "matchmaking-api.yaml"
    ).read_text(encoding="utf-8")
    assert "request_id:" in matchmaking_yaml
    assert "requested_at:" in matchmaking_yaml
    assert "enum: [ACTIVE, TERMINATED, EXPIRED, PENDING]" in matchmaking_yaml
    assert "NEW_REQUEST" in matchmaking_yaml
    assert "/api/v1/trainers/me/notifications:" in matchmaking_yaml
    assert "/api/v1/trainers/me/notifications/{notification_id}/read:" in matchmaking_yaml

    # 4. Verificar que las rutas frontend en README.md coincidan con frontend/src/constants/routes.ts
    routes_ts = (repo_root / "frontend" / "src" / "constants" / "routes.ts").read_text(
        encoding="utf-8"
    )
    readme_md = (repo_root / "README.md").read_text(encoding="utf-8")
    ts_paths = re.findall(r":\s*'(/[^']+)'", routes_ts)
    assert len(ts_paths) >= 8
    for frontend_path in ts_paths:
        assert f"`{frontend_path}`" in readme_md, (
            f"La ruta frontend {frontend_path} de routes.ts no está documentada en README.md"
        )
