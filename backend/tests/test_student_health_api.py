from fastapi import status

from backend.src.models import HealthQuestionnaire, StudentProfile
from backend.src.services.student_service import (
    StudentProfileError,
    require_health_questionnaire,
)

URL = "/api/v1/students/me/health-questionnaire"
ANSWERS = {
    "has_heart_condition": False,
    "has_chest_pain_activity": False,
    "has_dizziness_or_balance_loss": False,
    "has_bone_joint_problem": False,
    "takes_prescription_meds": False,
}


def register_and_login(test_client, email, role):
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    token = test_client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_save_questionnaire_creates_current_version(client, student_token_headers):
    test_client, _ = client
    response = test_client.post(URL, headers=student_token_headers, json=ANSWERS)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["status"] == "CURRENT"
    assert response.json()["has_risk_answers"] is False

    risky = {**ANSWERS, "has_bone_joint_problem": True, "other_medical_conditions": "Tendinitis"}
    response = test_client.post(URL, headers=student_token_headers, json=risky)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["has_risk_answers"] is True


def test_missing_or_null_answer_is_rejected(client, student_token_headers):
    test_client, _ = client
    for field in ANSWERS:
        partial = {key: value for key, value in ANSWERS.items() if key != field}
        assert test_client.post(URL, headers=student_token_headers, json=partial).status_code == 422
        assert test_client.post(URL, headers=student_token_headers, json={**ANSWERS, field: None}).status_code == 422


def test_update_archives_previous_version(client, student_token_headers):
    test_client, session_factory = client
    test_client.post(URL, headers=student_token_headers, json=ANSWERS)
    test_client.post(URL, headers=student_token_headers, json={**ANSWERS, "takes_prescription_meds": True})

    current = test_client.get(URL, headers=student_token_headers).json()
    assert current["takes_prescription_meds"] is True
    with session_factory() as db:
        statuses = sorted(row.status for row in db.query(HealthQuestionnaire).all())
    assert statuses == ["ARCHIVED", "CURRENT"]


def test_get_without_questionnaire_is_404(client, student_token_headers):
    test_client, _ = client
    assert test_client.get(URL, headers=student_token_headers).status_code == status.HTTP_404_NOT_FOUND


def test_profile_exposes_completion_flag(client, student_token_headers):
    test_client, _ = client
    profile_url = "/api/v1/students/me/profile"
    assert test_client.get(profile_url, headers=student_token_headers).json()["health_questionnaire_completed"] is False
    test_client.post(URL, headers=student_token_headers, json=ANSWERS)
    assert test_client.get(profile_url, headers=student_token_headers).json()["health_questionnaire_completed"] is True


def test_trainer_cannot_use_own_questionnaire(client):
    test_client, _ = client
    trainer = register_and_login(test_client, "entrenador@example.com", "TRAINER")
    assert test_client.post(URL, headers=trainer, json=ANSWERS).status_code == status.HTTP_403_FORBIDDEN


def test_questionnaire_visibility(client, student_token_headers):
    test_client, _ = client
    profile_id = test_client.get("/api/v1/students/me/profile", headers=student_token_headers).json()["id"]
    url = f"/api/v1/students/{profile_id}/health-questionnaire"

    assert test_client.get(url, headers=student_token_headers).status_code == status.HTTP_404_NOT_FOUND
    test_client.post(URL, headers=student_token_headers, json=ANSWERS)
    assert test_client.get(url, headers=student_token_headers).status_code == status.HTTP_200_OK

    trainer = register_and_login(test_client, "entrenador@example.com", "TRAINER")
    assert test_client.get(url, headers=trainer).status_code == status.HTTP_403_FORBIDDEN
    other = register_and_login(test_client, "otra@example.com", "STUDENT")
    assert test_client.get(url, headers=other).status_code == status.HTTP_403_FORBIDDEN
    missing = "/api/v1/students/does-not-exist/health-questionnaire"
    assert test_client.get(missing, headers=student_token_headers).status_code == status.HTTP_404_NOT_FOUND


def test_require_health_questionnaire_gate(client, student_token_headers):
    test_client, session_factory = client
    test_client.get("/api/v1/students/me/profile", headers=student_token_headers)
    with session_factory() as db:
        profile = db.query(StudentProfile).one()
        try:
            require_health_questionnaire(db, profile)
        except StudentProfileError as error:
            assert error.status_code == status.HTTP_403_FORBIDDEN
        else:
            raise AssertionError("expected 403 without questionnaire")

    test_client.post(URL, headers=student_token_headers, json=ANSWERS)
    with session_factory() as db:
        require_health_questionnaire(db, db.query(StudentProfile).one())
