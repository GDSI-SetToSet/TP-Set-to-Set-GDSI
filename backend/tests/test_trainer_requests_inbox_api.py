import io
from datetime import UTC, datetime, timedelta

from fastapi import status

from backend.src.models.training_request import TrainingRequest

REQUESTS_PATH = "/api/v1/matchmaking/requests"
REQUEST_DETAIL_PATH = "/api/v1/matchmaking/requests/{}"

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


def test_trainer_lists_own_pending_requests_ordered_and_isolated(client):
    api, session_factory = client
    trainer_a_token, trainer_a_id = setup_published_trainer(api, "coach_a@example.com", full_name="Coach A")
    plan_a_id = create_plan(api, trainer_a_token, title="Plan Hipertrofia", price=30000)

    trainer_b_token, trainer_b_id = setup_published_trainer(api, "coach_b@example.com", full_name="Coach B")
    plan_b_id = create_plan(api, trainer_b_token, title="Plan Funcional", price=22000)

    student_1_token, student_1_id = setup_student_complete(api, "s1@example.com", "Ana", "López")
    student_2_token, student_2_id = setup_student_complete(api, "s2@example.com", "Bruno", "Díaz")

    r1 = api.post(
        REQUESTS_PATH,
        headers=auth(student_1_token),
        json={"trainer_id": trainer_a_id, "plan_id": plan_a_id, "student_message": "Primera solicitud"},
    ).json()
    r2 = api.post(
        REQUESTS_PATH,
        headers=auth(student_2_token),
        json={"trainer_id": trainer_a_id, "plan_id": plan_a_id, "student_message": "Segunda solicitud"},
    ).json()
    r_other = api.post(
        REQUESTS_PATH,
        headers=auth(student_1_token),
        json={"trainer_id": trainer_b_id, "plan_id": plan_b_id, "student_message": "Para otro entrenador"},
    ).json()

    # Ensure deterministic descending order by created_at
    base_time = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        req1 = db.get(TrainingRequest, r1["id"])
        req2 = db.get(TrainingRequest, r2["id"])
        req1.created_at = base_time - timedelta(minutes=10)
        req2.created_at = base_time
        db.commit()

    resp_a = api.get(REQUESTS_PATH, headers=auth(trainer_a_token), params={"status": "PENDING"})
    assert resp_a.status_code == status.HTTP_200_OK
    items_a = resp_a.json()
    assert [item["id"] for item in items_a] == [r2["id"], r1["id"]]
    assert set(items_a[0].keys()) == {
        "id",
        "student_id",
        "trainer_id",
        "plan_id",
        "agreed_monthly_price",
        "agreed_currency",
        "status",
        "can_be_accepted",
        "student_message",
        "trainer_response_message",
        "created_at",
        "resolved_at",
    }
    assert items_a[0]["student_id"] == student_2_id
    assert items_a[1]["student_id"] == student_1_id
    assert items_a[0]["agreed_monthly_price"] == 30000
    assert items_a[0]["agreed_currency"] == "ARS"
    assert items_a[0]["can_be_accepted"] is True

    resp_b = api.get(REQUESTS_PATH, headers=auth(trainer_b_token), params={"status": "PENDING"})
    assert resp_b.status_code == status.HTTP_200_OK
    items_b = resp_b.json()
    assert [item["id"] for item in items_b] == [r_other["id"]]


def test_trainer_pending_count_reflects_only_pending_requests(client):
    api, session_factory = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)

    initial = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"})
    assert initial.status_code == status.HTTP_200_OK
    assert len(initial.json()) == 0

    student_1_token, _ = setup_student_complete(api, "s1@example.com")
    student_2_token, _ = setup_student_complete(api, "s2@example.com")

    r1 = api.post(
        REQUESTS_PATH,
        headers=auth(student_1_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()
    after_one = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"})
    assert len(after_one.json()) == 1

    r2 = api.post(
        REQUESTS_PATH,
        headers=auth(student_2_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()
    after_two = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"})
    assert len(after_two.json()) == 2

    # Mark first request as REJECTED directly in DB to verify status filtering
    with session_factory() as db:
        req1 = db.get(TrainingRequest, r1["id"])
        req1.status = "REJECTED"
        db.commit()

    only_pending = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"})
    assert len(only_pending.json()) == 1
    assert only_pending.json()[0]["id"] == r2["id"]


def test_student_cannot_access_trainer_inbox_or_detail(client):
    api, _ = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)
    student_token, _ = setup_student_complete(api, "student@example.com")

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    inbox_resp = api.get(REQUESTS_PATH, headers=auth(student_token), params={"status": "PENDING"})
    assert inbox_resp.status_code == status.HTTP_403_FORBIDDEN

    detail_resp = api.get(REQUEST_DETAIL_PATH.format(created["id"]), headers=auth(student_token))
    assert detail_resp.status_code == status.HTTP_403_FORBIDDEN


def test_trainer_request_detail_includes_student_summary_and_plan(client):
    api, _ = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token, title="Plan Fuerza Avanzado", price=35000)
    student_token, student_id = setup_student_complete(api, "student@example.com", "Camila", "Sosa")

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={
            "trainer_id": trainer_id,
            "plan_id": plan_id,
            "student_message": "Quiero preparar una competencia",
        },
    ).json()

    resp = api.get(REQUEST_DETAIL_PATH.format(created["id"]), headers=auth(trainer_token))
    assert resp.status_code == status.HTTP_200_OK
    detail = resp.json()
    assert set(detail.keys()) == {
        "id",
        "student_id",
        "trainer_id",
        "plan_id",
        "agreed_monthly_price",
        "agreed_currency",
        "status",
        "can_be_accepted",
        "student_message",
        "trainer_response_message",
        "created_at",
        "resolved_at",
        "student",
        "plan_title",
    }
    assert detail["id"] == created["id"]
    assert detail["student_id"] == student_id
    assert detail["trainer_id"] == trainer_id
    assert detail["plan_id"] == plan_id
    assert detail["plan_title"] == "Plan Fuerza Avanzado"
    assert detail["agreed_monthly_price"] == 35000
    assert detail["agreed_currency"] == "ARS"
    assert detail["status"] == "PENDING"
    assert detail["can_be_accepted"] is True
    assert detail["student_message"] == "Quiero preparar una competencia"
    assert detail["student"] == {
        "id": student_id,
        "first_name": "Camila",
        "last_name": "Sosa",
        "contact_phone": "+5491100001111",
        "birth_date": "2000-01-15T00:00:00",
    }


def test_trainer_cannot_view_other_trainer_request_or_nonexistent(client):
    api, _ = client
    trainer_a_token, trainer_a_id = setup_published_trainer(api, "coach_a@example.com")
    plan_a_id = create_plan(api, trainer_a_token)
    trainer_b_token, _ = setup_published_trainer(api, "coach_b@example.com")
    student_token, _ = setup_student_complete(api, "student@example.com")

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_a_id, "plan_id": plan_a_id},
    ).json()

    forbidden = api.get(REQUEST_DETAIL_PATH.format(created["id"]), headers=auth(trainer_b_token))
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN

    not_found = api.get(REQUEST_DETAIL_PATH.format("nonexistent-request-id"), headers=auth(trainer_a_token))
    assert not_found.status_code == status.HTTP_404_NOT_FOUND


def test_trainer_with_pending_request_can_access_student_goals_health_and_clearance(client):
    api, _ = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)
    student_token, student_id = setup_student_complete(api, "student@example.com")

    pdf_bytes = b"%PDF-1.4 apto medico vigente"
    files = {"file": ("apto_maria.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    upload_resp = api.post(
        "/api/v1/students/me/medical-clearance",
        headers=auth(student_token),
        files=files,
        data={"issue_date": "2026-10-01"},
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED

    api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    )

    goals_resp = api.get(f"/api/v1/students/{student_id}/goals", headers=auth(trainer_token))
    assert goals_resp.status_code == status.HTTP_200_OK
    assert goals_resp.json() == {
        "fitness_goals": ["fuerza", "salud_general"],
        "personal_motivation": "Mejorar postura y fuerza general",
    }

    health_resp = api.get(f"/api/v1/students/{student_id}/health-questionnaire", headers=auth(trainer_token))
    assert health_resp.status_code == status.HTTP_200_OK
    assert health_resp.json()["has_bone_joint_problem"] is True
    assert health_resp.json()["other_medical_conditions"] == "Molestia leve en hombro derecho"

    clearance_resp = api.get(f"/api/v1/students/{student_id}/medical-clearance/download", headers=auth(trainer_token))
    assert clearance_resp.status_code == status.HTTP_200_OK
    assert clearance_resp.content == pdf_bytes
    assert "application/pdf" in clearance_resp.headers["content-type"]


def test_trainer_without_pending_request_or_after_rejection_is_denied_access(client):
    api, session_factory = client
    trainer_a_token, trainer_a_id = setup_published_trainer(api, "coach_a@example.com")
    plan_a_id = create_plan(api, trainer_a_token)
    trainer_b_token, trainer_b_id = setup_published_trainer(api, "coach_b@example.com")
    plan_b_id = create_plan(api, trainer_b_token)
    unconfigured_trainer_token = register_and_login(api, "coach_no_profile@example.com", "TRAINER")

    student_1_token, student_1_id = setup_student_complete(api, "student1@example.com", "María", "García")
    student_2_token, student_2_id = setup_student_complete(api, "student2@example.com", "Pedro", "Gómez")

    files = {"file": ("apto.pdf", io.BytesIO(b"%PDF-1.4 apto"), "application/pdf")}
    api.post(
        "/api/v1/students/me/medical-clearance",
        headers=auth(student_1_token),
        files=files,
        data={"issue_date": "2026-10-01"},
    )
    api.post(
        "/api/v1/students/me/medical-clearance",
        headers=auth(student_2_token),
        files={"file": ("apto2.pdf", io.BytesIO(b"%PDF-1.4 apto 2"), "application/pdf")},
        data={"issue_date": "2026-10-01"},
    )

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_1_token),
        json={"trainer_id": trainer_a_id, "plan_id": plan_a_id},
    ).json()
    # student_2 sends a request only to trainer_b
    api.post(
        REQUESTS_PATH,
        headers=auth(student_2_token),
        json={"trainer_id": trainer_b_id, "plan_id": plan_b_id},
    )

    # While PENDING, trainer_a has access to student_1
    for endpoint in (
        f"/api/v1/students/{student_1_id}/goals",
        f"/api/v1/students/{student_1_id}/health-questionnaire",
        f"/api/v1/students/{student_1_id}/medical-clearance/download",
    ):
        assert api.get(endpoint, headers=auth(trainer_a_token)).status_code == status.HTTP_200_OK

    # Cross-student isolation: trainer_a (even with a PENDING request from student_1)
    # CANNOT access student_2's data (whose request belongs to trainer_b)
    for endpoint in (
        f"/api/v1/students/{student_2_id}/goals",
        f"/api/v1/students/{student_2_id}/health-questionnaire",
        f"/api/v1/students/{student_2_id}/medical-clearance/download",
    ):
        assert api.get(endpoint, headers=auth(trainer_a_token)).status_code == status.HTTP_403_FORBIDDEN

    # Cross-trainer isolation: trainer_b and unconfigured trainer CANNOT access student_1's data
    for token in (trainer_b_token, unconfigured_trainer_token):
        for endpoint in (
            f"/api/v1/students/{student_1_id}/goals",
            f"/api/v1/students/{student_1_id}/health-questionnaire",
            f"/api/v1/students/{student_1_id}/medical-clearance/download",
        ):
            assert api.get(endpoint, headers=auth(token)).status_code == status.HTTP_403_FORBIDDEN

    # Once request transitions to REJECTED or CANCELLED, trainer_a loses access immediately
    for non_pending_status in ("REJECTED", "CANCELLED"):
        with session_factory() as db:
            req = db.get(TrainingRequest, created["id"])
            req.status = non_pending_status
            db.commit()

        for endpoint in (
            f"/api/v1/students/{student_1_id}/goals",
            f"/api/v1/students/{student_1_id}/health-questionnaire",
            f"/api/v1/students/{student_1_id}/medical-clearance/download",
        ):
            assert api.get(endpoint, headers=auth(trainer_a_token)).status_code == status.HTTP_403_FORBIDDEN


def test_inbox_and_detail_when_trainer_quota_is_full(client):
    api, _ = client
    trainer_token, trainer_id = setup_published_trainer(api, "coach@example.com", max_students=2)
    plan_id = create_plan(api, trainer_token)
    student_token, _ = setup_student_complete(api, "student@example.com")

    created = api.post(
        REQUESTS_PATH,
        headers=auth(student_token),
        json={"trainer_id": trainer_id, "plan_id": plan_id},
    ).json()

    # Lower quota to 0 so active_students (0) >= max_students (0) -> quota full
    api.patch("/api/v1/trainers/me/quota", headers=auth(trainer_token), json={"max_students": 0})

    inbox_resp = api.get(REQUESTS_PATH, headers=auth(trainer_token), params={"status": "PENDING"})
    assert inbox_resp.status_code == status.HTTP_200_OK
    items = inbox_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["status"] == "PENDING"
    assert items[0]["can_be_accepted"] is False

    detail_resp = api.get(REQUEST_DETAIL_PATH.format(created["id"]), headers=auth(trainer_token))
    assert detail_resp.status_code == status.HTTP_200_OK
    assert detail_resp.json()["can_be_accepted"] is False

    # Re-open quota and verify can_be_accepted becomes True dynamically
    api.patch("/api/v1/trainers/me/quota", headers=auth(trainer_token), json={"max_students": 3})
    reopened_detail = api.get(REQUEST_DETAIL_PATH.format(created["id"]), headers=auth(trainer_token))
    assert reopened_detail.status_code == status.HTTP_200_OK
    assert reopened_detail.json()["can_be_accepted"] is True
