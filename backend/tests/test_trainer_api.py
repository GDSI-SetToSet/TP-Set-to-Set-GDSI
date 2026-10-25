from backend.src.models.user import User
from sqlalchemy import select


def register_and_login(api, email: str, role: str) -> str:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_trainer_profile_full_flow(client):
    api, _ = client
    trainer_token = register_and_login(api, "coach@example.com", "TRAINER")
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    initial = api.get("/api/v1/trainers/me/profile", headers=auth(trainer_token))
    assert initial.status_code == 200
    assert initial.json()["status"] == "DRAFT"

    partial = api.put(
        "/api/v1/trainers/me/profile",
        headers=auth(trainer_token),
        json={"bio": "Profesor de educación física"},
    )
    assert partial.status_code == 200
    assert partial.json()["status"] == "DRAFT"
    profile_id = partial.json()["id"]
    assert api.get(f"/api/v1/trainers/{profile_id}/profile", headers=auth(student_token)).status_code == 404

    published = api.put(
        "/api/v1/trainers/me/profile",
        headers=auth(trainer_token),
        json={"full_name": "Lucas Pérez", "contact_phone": "+5491155551234", "specialty": "Fuerza"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"
    public = api.get(f"/api/v1/trainers/{profile_id}/profile", headers=auth(student_token))
    assert public.status_code == 200
    assert public.json()["full_name"] == "Lucas Pérez"
    assert api.get(f"/api/v1/trainers/{profile_id}/profile").status_code == 401


def test_profile_endpoints_enforce_role_and_validation(client):
    api, _ = client
    trainer_token = register_and_login(api, "coach@example.com", "TRAINER")
    student_token = register_and_login(api, "student@example.com", "STUDENT")
    assert api.get("/api/v1/trainers/me/profile", headers=auth(student_token)).status_code == 403

    invalid = api.put(
        "/api/v1/trainers/me/profile",
        headers=auth(trainer_token),
        json={"contact_phone": "11-5555"},
    )
    assert invalid.status_code == 422
    assert invalid.headers["content-type"].startswith("application/problem+json")
    assert invalid.json()["errors"][0]["field"] == "contact_phone"


def test_published_profile_rejects_removing_required_data(client):
    api, sessions = client
    token = register_and_login(api, "coach@example.com", "TRAINER")
    api.put(
        "/api/v1/trainers/me/profile",
        headers=auth(token),
        json={"full_name": "Lucas Pérez", "contact_phone": "+5491155551234", "specialty": "Fuerza"},
    )
    response = api.put("/api/v1/trainers/me/profile", headers=auth(token), json={"specialty": None})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"] == [{"field": "specialty", "message": "Este campo es obligatorio."}]
    with sessions() as db:
        trainer = db.scalar(select(User).where(User.email == "coach@example.com"))
        assert trainer.trainer_profile.specialty == "Fuerza"

