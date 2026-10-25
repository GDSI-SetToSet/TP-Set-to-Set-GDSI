import io
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.schema import CreateIndex

from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.training_request import TrainingRequest
from backend.src.models.user import User
from backend.src.schemas.discovery import (
    TrainingRequestAcceptPayload,
    TrainingRequestRejectPayload,
)
from backend.src.services.discovery_service import (
    DiscoveryError,
    accept_training_request,
    reject_training_request,
)

REQUESTS_PATH = "/api/v1/matchmaking/requests"
ACCEPT_PATH = "/api/v1/matchmaking/requests/{}/accept"
REJECT_PATH = "/api/v1/matchmaking/requests/{}/reject"

TRAINER_PUBLISHED = {
    "full_name": "Lucas Pérez",
    "contact_phone": "+5491155551234",
    "specialty": "Fuerza",
}
STUDENT_PROFILE = {
    "first_name": "María",
    "last_name": "García",
    "birth_date": "2000-01-15T00:00:00Z",
    "contact_phone": "+5491100001111",
    "fitness_goals": ["fuerza", "salud_general"],
    "personal_motivation": "Mejorar postura y fuerza general",
}
HEALTH_QUESTIONNAIRE = {
    "has_heart_condition": False,
    "has_chest_pain_activity": False,
    "has_dizziness_or_balance_loss": False,
    "has_bone_joint_problem": True,
    "takes_prescription_meds": False,
    "other_medical_conditions": "Molestia leve en hombro derecho",
}


def register_and_login(api, email: str, role: str) -> str:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def setup_published_trainer(
    api, email: str, max_students: int = 5, full_name: str = TRAINER_PUBLISHED["full_name"]
) -> tuple[str, str]:
    token = register_and_login(api, email, "TRAINER")
    body = {**TRAINER_PUBLISHED, "full_name": full_name}
    profile = api.put("/api/v1/trainers/me/profile", headers=auth(token), json=body).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(token), json={"max_students": max_students})
    return token, profile["id"]


def setup_student_complete(
    api, email: str, first_name: str = "María", last_name: str = "García"
) -> tuple[str, str]:
    token = register_and_login(api, email, "STUDENT")
    payload = {**STUDENT_PROFILE, "first_name": first_name, "last_name": last_name}
    profile = api.put("/api/v1/students/me/profile", headers=auth(token), json=payload).json()
    api.post("/api/v1/students/me/health-questionnaire", headers=auth(token), json=HEALTH_QUESTIONNAIRE)
    return token, profile["id"]


def create_plan(api, trainer_token: str, title: str = "Plan Fuerza", price: int = 25000) -> str:
    resp = api.post(
        "/api/v1/trainers/me/plans",
        headers=auth(trainer_token),
        json={"title": title, "monthly_price": price},
    )
    return resp.json()["id"]


# ── Acceptance tests ──


def test_accept_request_creates_active_relationship_updates_quota_and_removes_from_pending(client):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=2)
    plan_id = create_plan(api, trainer_token, title="Plan Hipertrofia", price=32000)
    student_token, student_id = setup_student_complete(api, "student@example.com")

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id, "student_message": "Quiero arrancar"},
    ).json()

    # Edit plan price afterwards to verify non-retroactivity (FR-010)
    api.put(
        f"/api/v1/trainers/me/plans/{plan_id}",
        headers=auth(trainer_token),
        json={"title": "Plan Hipertrofia", "monthly_price": 45000},
    )

    resp = api.post(
        ACCEPT_PATH.format(created["id"]),
        headers=auth(trainer_token),
        json={"welcome_message": "¡Bienvenida al equipo!"},
    )
    assert resp.status_code == status.HTTP_200_OK
    rel = resp.json()
    assert set(rel.keys()) == {
        "id",
        "student_id",
        "trainer_id",
        "plan_id",
        "agreed_monthly_price",
        "agreed_currency",
        "status",
        "start_date",
    }
    assert rel["student_id"] == student_id
    assert rel["trainer_id"] == trainer_id
    assert rel["plan_id"] == plan_id
    assert rel["agreed_monthly_price"] == 32000
    assert rel["agreed_currency"] == "ARS"
    assert rel["status"] == "ACTIVE"

    # Verify DB state: exactly 1 ACTIVE relationship and request is ACCEPTED with welcome message
    with session_factory() as db:
        relationships = db.scalars(select(TrainingRelationship)).all()
        assert len(relationships) == 1
        assert relationships[0].status == "ACTIVE"
        req = db.get(TrainingRequest, created["id"])
        assert req.status == "ACCEPTED"
        assert req.trainer_response_message == "¡Bienvenida al equipo!"
        assert req.resolved_at is not None

    # Verify request no longer appears in PENDING inbox
    pending_inbox = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"}).json()
    assert pending_inbox == []

    # Verify trainer active students and available slots updated
    trainer_profile = api.get("/api/v1/trainers/me/profile", headers=auth(trainer_token)).json()
    assert trainer_profile["active_students_count"] == 1
    assert trainer_profile["available_slots"] == 1
    assert trainer_profile["has_available_quota"] is True


def test_accept_request_without_body_succeeds(client):
    api, _ = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=2)
    plan_id = create_plan(api, trainer_token)
    student_token, _ = setup_student_complete(api, "student@example.com")

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    resp = api.post(ACCEPT_PATH.format(created["id"]), headers=auth(trainer_token))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == "ACTIVE"


def test_accept_when_quota_full_returns_409_and_does_not_mutate_db(client):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=1)
    plan_id = create_plan(api, trainer_token)
    s1_token, _ = setup_student_complete(api, "s1@example.com", "Ana", "Uno")
    s2_token, _ = setup_student_complete(api, "s2@example.com", "Beto", "Dos")

    req1 = api.post(
        REQUESTS_PATH,
        headers=auth(s1_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()
    req2 = api.post(
        REQUESTS_PATH,
        headers=auth(s2_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    # Accept first request: fills the single quota slot (active_students = 1 == max_students)
    first_accept = api.post(ACCEPT_PATH.format(req1["id"]), headers=auth(trainer_token))
    assert first_accept.status_code == status.HTTP_200_OK

    # Second request remains visible in PENDING with can_be_accepted = False
    pending = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"}).json()
    assert len(pending) == 1
    assert pending[0]["id"] == req2["id"]
    assert pending[0]["can_be_accepted"] is False

    # Forcing accept on second request fails with 409 RFC 7807
    second_accept = api.post(ACCEPT_PATH.format(req2["id"]), headers=auth(trainer_token))
    assert second_accept.status_code == status.HTTP_409_CONFLICT
    assert second_accept.headers["content-type"].startswith("application/problem+json")
    assert second_accept.json()["detail"] == "Cupos agotados; libere un cupo para poder aceptar."

    # Verify DB untouched for req2 and only 1 relationship exists
    with session_factory() as db:
        relationships = db.scalars(select(TrainingRelationship)).all()
        assert len(relationships) == 1
        stored_req2 = db.get(TrainingRequest, req2["id"])
        assert stored_req2.status == "PENDING"
        assert stored_req2.resolved_at is None


# ── Rejection tests ──


def test_reject_request_with_and_without_reason_keeps_quota_intact(client):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=2)
    plan_id = create_plan(api, trainer_token)
    s1_token, _ = setup_student_complete(api, "s1@example.com")
    s2_token, _ = setup_student_complete(api, "s2@example.com")

    req1 = api.post(
        REQUESTS_PATH,
        headers=auth(s1_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()
    req2 = api.post(
        REQUESTS_PATH,
        headers=auth(s2_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    # Reject first with explicit reason
    r1 = api.post(
        REJECT_PATH.format(req1["id"]),
        headers=auth(trainer_token),
        json={"rejection_reason": "No realizo rehabilitación de hombro"},
    )
    assert r1.status_code == status.HTTP_200_OK
    data1 = r1.json()
    assert data1["status"] == "REJECTED"
    assert data1["trainer_response_message"] == "No realizo rehabilitación de hombro"
    assert data1["resolved_at"] is not None
    assert data1["can_be_accepted"] is False

    # Reject second without body (optional reason)
    r2 = api.post(REJECT_PATH.format(req2["id"]), headers=auth(trainer_token))
    assert r2.status_code == status.HTTP_200_OK
    data2 = r2.json()
    assert data2["status"] == "REJECTED"
    assert data2["trainer_response_message"] is None
    assert data2["resolved_at"] is not None

    # Pending inbox is now empty and quota is untouched (0 active students)
    pending = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"}).json()
    assert pending == []

    profile = api.get("/api/v1/trainers/me/profile", headers=auth(trainer_token)).json()
    assert profile["active_students_count"] == 0
    assert profile["available_slots"] == 2

    with session_factory() as db:
        assert db.scalars(select(TrainingRelationship)).all() == []


# ── Idempotency & already processed tests ──


def test_cannot_accept_or_reject_already_processed_request(client):
    api, _ = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=3)
    plan_id = create_plan(api, trainer_token)
    s1_token, _ = setup_student_complete(api, "s1@example.com")
    s2_token, _ = setup_student_complete(api, "s2@example.com")

    req_accepted = api.post(
        REQUESTS_PATH,
        headers=auth(s1_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()
    req_rejected = api.post(
        REQUESTS_PATH,
        headers=auth(s2_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    assert api.post(ACCEPT_PATH.format(req_accepted["id"]), headers=auth(trainer_token)).status_code == 200
    assert api.post(REJECT_PATH.format(req_rejected["id"]), headers=auth(trainer_token)).status_code == 200

    for resolved_id in (req_accepted["id"], req_rejected["id"]):
        again_accept = api.post(ACCEPT_PATH.format(resolved_id), headers=auth(trainer_token))
        assert again_accept.status_code == status.HTTP_409_CONFLICT
        assert again_accept.json()["detail"] == "La solicitud ya fue procesada."

        again_reject = api.post(REJECT_PATH.format(resolved_id), headers=auth(trainer_token))
        assert again_reject.status_code == status.HTTP_409_CONFLICT
        assert again_reject.json()["detail"] == "La solicitud ya fue procesada."


# ── Concurrency tests ──


def test_concurrent_acceptances_do_not_exceed_last_quota_slot(client):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=1)
    plan_id = create_plan(api, trainer_token)
    s1_token, _ = setup_student_complete(api, "s1@example.com", "Ana", "Uno")
    s2_token, _ = setup_student_complete(api, "s2@example.com", "Beto", "Dos")

    req1 = api.post(
        REQUESTS_PATH,
        headers=auth(s1_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()
    req2 = api.post(
        REQUESTS_PATH,
        headers=auth(s2_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    with session_factory() as db:
        trainer_user_id = db.scalar(select(User.id).where(User.email == "coach@example.com"))

    def worker(target_request_id: str) -> int:
        with session_factory() as db:
            user = db.get(User, trainer_user_id)
            try:
                accept_training_request(
                    db, user, target_request_id, TrainingRequestAcceptPayload(welcome_message="Hola")
                )
                return status.HTTP_200_OK
            except DiscoveryError as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, req1["id"]), pool.submit(worker, req2["id"])]
        results = sorted(f.result() for f in futures)

    assert results == [status.HTTP_200_OK, status.HTTP_409_CONFLICT]

    with session_factory() as db:
        active_rels = db.scalars(
            select(TrainingRelationship).where(TrainingRelationship.status == "ACTIVE")
        ).all()
        assert len(active_rels) == 1


# ── Partial unique index & Rollback robustness tests ──


def test_partial_unique_index_prevents_duplicate_active_relationships_and_allows_terminated_history(
    client,
):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=5)
    plan_id = create_plan(api, trainer_token)
    student_token, student_id = setup_student_complete(api, "student@example.com")

    # Verify DDL generation for both SQLite and PostgreSQL dialects
    partial_indexes = [
        idx
        for idx in TrainingRelationship.__table__.indexes
        if idx.name == "uq_active_training_relationship"
    ]
    assert len(partial_indexes) == 1
    uq_idx = partial_indexes[0]
    sqlite_ddl = str(CreateIndex(uq_idx).compile(dialect=sqlite.dialect()))
    pg_ddl = str(CreateIndex(uq_idx).compile(dialect=postgresql.dialect()))
    assert "CREATE UNIQUE INDEX uq_active_training_relationship" in sqlite_ddl
    assert "WHERE status = 'ACTIVE'" in sqlite_ddl
    assert "CREATE UNIQUE INDEX uq_active_training_relationship" in pg_ddl
    assert "WHERE status = 'ACTIVE'" in pg_ddl

    with session_factory() as db:
        rel1 = TrainingRelationship(
            student_id=student_id,
            trainer_id=trainer_id,
            plan_id=plan_id,
            agreed_monthly_price=Decimal("25000.00"),
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=date(2026, 10, 1),
        )
        db.add(rel1)
        db.commit()

        # Attempting to persist a second ACTIVE relationship for the same pair fails in DB engine
        rel_duplicate = TrainingRelationship(
            student_id=student_id,
            trainer_id=trainer_id,
            plan_id=plan_id,
            agreed_monthly_price=Decimal("25000.00"),
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=date(2026, 10, 2),
        )
        db.add(rel_duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        # Terminating the first relationship and adding another historical TERMINATED one succeeds
        rel1_stored = db.get(TrainingRelationship, rel1.id)
        rel1_stored.status = "TERMINATED"
        rel_historical = TrainingRelationship(
            student_id=student_id,
            trainer_id=trainer_id,
            plan_id=plan_id,
            agreed_monthly_price=Decimal("25000.00"),
            agreed_currency="ARS",
            status="TERMINATED",
            start_date=date(2026, 9, 1),
        )
        db.add(rel_historical)
        db.commit()

    # Now creating and accepting a new request for the same (student, trainer) pair succeeds
    new_req = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    )
    assert new_req.status_code == status.HTTP_201_CREATED
    accept_resp = api.post(ACCEPT_PATH.format(new_req.json()["id"]), headers=auth(trainer_token))
    assert accept_resp.status_code == status.HTTP_200_OK

    with session_factory() as db:
        all_rels = db.scalars(
            select(TrainingRelationship).where(
                TrainingRelationship.student_id == student_id,
                TrainingRelationship.trainer_id == trainer_id,
            )
        ).all()
        assert len(all_rels) == 3
        assert sum(1 for r in all_rels if r.status == "ACTIVE") == 1
        assert sum(1 for r in all_rels if r.status == "TERMINATED") == 2


def test_accept_and_reject_rollback_on_commit_failure_keeps_db_atomic_and_session_reusable(
    client, monkeypatch
):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=3)
    plan_id = create_plan(api, trainer_token)
    s1_token, _ = setup_student_complete(api, "s1@example.com", "Ana", "Uno")
    s2_token, _ = setup_student_complete(api, "s2@example.com", "Beto", "Dos")

    req_accept = api.post(
        REQUESTS_PATH,
        headers=auth(s1_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()
    req_reject = api.post(
        REQUESTS_PATH,
        headers=auth(s2_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    with session_factory() as db:
        trainer_user = db.scalar(select(User).where(User.email == "coach@example.com"))
        real_commit = db.commit

        def failing_commit():
            raise OperationalError("COMMIT", {}, RuntimeError("simulated I/O failure"))

        # 1. Commit failure during accept rolls back both request status and TrainingRelationship
        monkeypatch.setattr(db, "commit", failing_commit)
        with pytest.raises(OperationalError):
            accept_training_request(
                db,
                trainer_user,
                req_accept["id"],
                TrainingRequestAcceptPayload(welcome_message="Hola"),
            )

        # Restore commit and reuse the exact same session without manual rollback
        monkeypatch.setattr(db, "commit", real_commit)
        persisted_accept_req = db.get(TrainingRequest, req_accept["id"])
        assert persisted_accept_req.status == "PENDING"
        assert persisted_accept_req.trainer_response_message is None
        assert persisted_accept_req.resolved_at is None
        assert db.scalars(select(TrainingRelationship)).all() == []

        # 2. Commit failure during reject rolls back partial modifications and keeps session usable
        monkeypatch.setattr(db, "commit", failing_commit)
        with pytest.raises(OperationalError):
            reject_training_request(
                db,
                trainer_user,
                req_reject["id"],
                TrainingRequestRejectPayload(rejection_reason="Sin disponibilidad"),
            )

        monkeypatch.setattr(db, "commit", real_commit)
        persisted_reject_req = db.get(TrainingRequest, req_reject["id"])
        assert persisted_reject_req.status == "PENDING"
        assert persisted_reject_req.trainer_response_message is None
        assert persisted_reject_req.resolved_at is None


def test_accept_translates_unique_active_relationship_integrity_error_to_409_and_reraises_other_integrity_errors(
    client, monkeypatch
):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=3)
    plan_id = create_plan(api, trainer_token)
    student_token, _ = setup_student_complete(api, "s1@example.com")

    req = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    with session_factory() as db:
        trainer_user = db.scalar(select(User).where(User.email == "coach@example.com"))
        real_commit = db.commit

        # A. IntegrityError from uq_active_training_relationship -> rolled back and translated to 409
        def duplicate_active_commit():
            raise IntegrityError(
                "INSERT INTO training_relationships",
                {},
                RuntimeError("UNIQUE constraint failed: index 'uq_active_training_relationship'"),
            )

        monkeypatch.setattr(db, "commit", duplicate_active_commit)
        with pytest.raises(DiscoveryError) as exc_info:
            accept_training_request(db, trainer_user, req["id"])
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "La solicitud ya fue procesada."

        # Session remains clean and request was not left ACCEPTED
        monkeypatch.setattr(db, "commit", real_commit)
        assert db.get(TrainingRequest, req["id"]).status == "PENDING"

        # B. Unrelated IntegrityError (e.g. foreign key failure) -> rolled back and re-raised as server error
        def unrelated_integrity_commit():
            raise IntegrityError(
                "INSERT INTO training_relationships",
                {},
                RuntimeError("FOREIGN KEY constraint failed"),
            )

        monkeypatch.setattr(db, "commit", unrelated_integrity_commit)
        with pytest.raises(IntegrityError):
            accept_training_request(db, trainer_user, req["id"])

        monkeypatch.setattr(db, "commit", real_commit)
        assert db.get(TrainingRequest, req["id"]).status == "PENDING"


# ── Security & post-acceptance authorization tests ──


def test_authorization_preserved_after_acceptance_and_revoked_after_rejection_or_termination(client):
    api, session_factory = client
    trainer_a_token, trainer_a_id = setup_published_trainer(api, "coach_a@example.com", max_students=3)
    plan_a_id = create_plan(api, trainer_a_token)
    trainer_b_token, _ = setup_published_trainer(api, "coach_b@example.com", max_students=3)

    student_1_token, student_1_id = setup_student_complete(api, "s1@example.com", "Laura", "Paz")
    student_2_token, student_2_id = setup_student_complete(api, "s2@example.com", "Diego", "Mar")

    for s_token in (student_1_token, student_2_token):
        api.post(
            "/api/v1/students/me/medical-clearance",
            headers=auth(s_token),
            files={"file": ("apto.pdf", io.BytesIO(b"%PDF-1.4 apto"), "application/pdf")},
            data={"issue_date": "2026-10-01"},
        )

    req_s1 = api.post(
        REQUESTS_PATH,
        headers=auth(student_1_token),
        json={"trainer_id": trainer_a_id, "plan_id": plan_a_id},
    ).json()
    req_s2 = api.post(
        REQUESTS_PATH,
        headers=auth(student_2_token),
        json={"trainer_id": trainer_a_id, "plan_id": plan_a_id},
    ).json()

    # Accept student_1 -> status becomes ACCEPTED, relationship becomes ACTIVE
    accept_resp = api.post(ACCEPT_PATH.format(req_s1["id"]), headers=auth(trainer_a_token))
    assert accept_resp.status_code == status.HTTP_200_OK
    rel_id = accept_resp.json()["id"]

    # Reject student_2 -> status becomes REJECTED, no relationship created
    reject_resp = api.post(
        REJECT_PATH.format(req_s2["id"]),
        headers=auth(trainer_a_token),
        json={"rejection_reason": "Cupo en horario incompatible"},
    )
    assert reject_resp.status_code == status.HTTP_200_OK

    # trainer_a STILL has access to student_1's goals, health questionnaire, and medical clearance via ACTIVE relation
    for endpoint in (
        f"/api/v1/students/{student_1_id}/goals",
        f"/api/v1/students/{student_1_id}/health-questionnaire",
        f"/api/v1/students/{student_1_id}/medical-clearance/download",
    ):
        assert api.get(endpoint, headers=auth(trainer_a_token)).status_code == status.HTTP_200_OK
        # Unrelated trainer_b is still denied access to student_1
        assert api.get(endpoint, headers=auth(trainer_b_token)).status_code == status.HTTP_403_FORBIDDEN

    # trainer_a immediately LOST access to student_2 after rejecting req_s2
    for endpoint in (
        f"/api/v1/students/{student_2_id}/goals",
        f"/api/v1/students/{student_2_id}/health-questionnaire",
        f"/api/v1/students/{student_2_id}/medical-clearance/download",
    ):
        assert api.get(endpoint, headers=auth(trainer_a_token)).status_code == status.HTTP_403_FORBIDDEN

    # If the ACTIVE relationship with student_1 later transitions to TERMINATED, trainer_a loses access
    with session_factory() as db:
        rel = db.get(TrainingRelationship, rel_id)
        rel.status = "TERMINATED"
        db.commit()

    for endpoint in (
        f"/api/v1/students/{student_1_id}/goals",
        f"/api/v1/students/{student_1_id}/health-questionnaire",
        f"/api/v1/students/{student_1_id}/medical-clearance/download",
    ):
        assert api.get(endpoint, headers=auth(trainer_a_token)).status_code == status.HTTP_403_FORBIDDEN


def test_only_recipient_published_trainer_can_accept_or_reject(client):
    api, _ = client
    trainer_a_token, trainer_a_id = setup_published_trainer(api, "coach_a@example.com")
    plan_a_id = create_plan(api, trainer_a_token)
    trainer_b_token, _ = setup_published_trainer(api, "coach_b@example.com")
    unconfigured_trainer_token = register_and_login(api, "unconfigured@example.com", "TRAINER")
    draft_trainer_token = register_and_login(api, "draft@example.com", "TRAINER")
    api.put("/api/v1/trainers/me/profile", headers=auth(draft_trainer_token), json={"full_name": "Solo Nombre"})
    student_token, _ = setup_student_complete(api, "student@example.com")

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_a_id, "plan_id": plan_a_id},
    ).json()

    for unauthorized_token in (
        trainer_b_token,
        unconfigured_trainer_token,
        draft_trainer_token,
        student_token,
    ):
        assert (
            api.post(ACCEPT_PATH.format(created["id"]), headers=auth(unauthorized_token)).status_code
            == status.HTTP_403_FORBIDDEN
        )
        assert (
            api.post(REJECT_PATH.format(created["id"]), headers=auth(unauthorized_token)).status_code
            == status.HTTP_403_FORBIDDEN
        )

    # Nonexistent request returns 404 for a published trainer
    assert (
        api.post(ACCEPT_PATH.format("nonexistent-id"), headers=auth(trainer_a_token)).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        api.post(REJECT_PATH.format("nonexistent-id"), headers=auth(trainer_a_token)).status_code
        == status.HTTP_404_NOT_FOUND
    )
