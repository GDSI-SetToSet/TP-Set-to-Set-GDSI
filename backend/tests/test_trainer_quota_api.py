from sqlalchemy import select

from backend.src.models.user import User

QUOTA_PATH = "/api/v1/trainers/me/quota"
PUBLISHED_DATA = {"full_name": "Lucas Pérez", "contact_phone": "+5491155551234", "specialty": "Fuerza"}


def register_and_login(api, email: str, role: str) -> str:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_quota_update_is_visible_in_public_profile(client):
    api, _ = client
    trainer_token = register_and_login(api, "coach@example.com", "TRAINER")
    student_token = register_and_login(api, "student@example.com", "STUDENT")
    profile_id = api.put("/api/v1/trainers/me/profile", headers=auth(trainer_token), json=PUBLISHED_DATA).json()["id"]

    public = api.get(f"/api/v1/trainers/{profile_id}/profile", headers=auth(student_token)).json()
    assert public["max_students"] == 0
    assert public["has_available_quota"] is False

    updated = api.patch(QUOTA_PATH, headers=auth(trainer_token), json={"max_students": 20})
    assert updated.status_code == 200
    assert updated.json() == {"max_students": 20, "active_students": 0, "available_slots": 20, "has_available_quota": True}

    public = api.get(f"/api/v1/trainers/{profile_id}/profile", headers=auth(student_token)).json()
    assert public["available_slots"] == 20
    assert public["active_students_count"] == 0
    assert public["has_available_quota"] is True


def test_missing_quota_is_saved_as_zero(client):
    api, _ = client
    token = register_and_login(api, "coach@example.com", "TRAINER")
    api.patch(QUOTA_PATH, headers=auth(token), json={"max_students": 10})
    response = api.patch(QUOTA_PATH, headers=auth(token), json={})
    assert response.status_code == 200
    assert response.json()["max_students"] == 0
    assert response.json()["has_available_quota"] is False


def test_quota_out_of_range_keeps_current_value(client):
    api, sessions = client
    token = register_and_login(api, "coach@example.com", "TRAINER")
    api.patch(QUOTA_PATH, headers=auth(token), json={"max_students": 10})

    response = api.patch(QUOTA_PATH, headers=auth(token), json={"max_students": 101})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"] == [{"field": "max_students", "message": "Los cupos deben estar entre 0 y 100"}]
    with sessions() as db:
        trainer = db.scalar(select(User).where(User.email == "coach@example.com"))
        assert trainer.trainer_profile.max_students == 10


def test_quota_requires_trainer_role(client):
    api, _ = client
    student_token = register_and_login(api, "student@example.com", "STUDENT")
    assert api.patch(QUOTA_PATH, headers=auth(student_token), json={"max_students": 5}).status_code == 403
    assert api.patch(QUOTA_PATH, json={"max_students": 5}).status_code == 401
