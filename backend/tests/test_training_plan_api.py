PLANS_PATH = "/api/v1/trainers/me/plans"
PUBLISHED_DATA = {"full_name": "Lucas Pérez", "contact_phone": "+5491155551234", "specialty": "Fuerza"}


def register_and_login(api, email: str, role: str) -> str:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_plan_full_flow_and_public_visibility(client):
    api, _ = client
    trainer_token = register_and_login(api, "coach@example.com", "TRAINER")
    student_token = register_and_login(api, "student@example.com", "STUDENT")
    profile_id = api.put("/api/v1/trainers/me/profile", headers=auth(trainer_token), json=PUBLISHED_DATA).json()["id"]

    created = api.post(
        PLANS_PATH,
        headers=auth(trainer_token),
        json={"title": "Plan Fuerza 3 Días", "description": "Rutina + seguimiento", "monthly_price": 28000},
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["currency"] == "ARS"
    assert plan["monthly_price"] == 28000
    assert plan["trainer_id"] == profile_id

    public = api.get(f"/api/v1/trainers/{profile_id}/plans", headers=auth(student_token))
    assert public.status_code == 200
    assert [item["id"] for item in public.json()] == [plan["id"]]

    edited = api.put(f"{PLANS_PATH}/{plan['id']}", headers=auth(trainer_token), json={"monthly_price": 30000})
    assert edited.status_code == 200
    assert edited.json()["monthly_price"] == 30000

    archived = api.post(f"{PLANS_PATH}/{plan['id']}/archive", headers=auth(trainer_token))
    assert archived.status_code == 200
    assert archived.json()["is_active"] is False
    assert api.get(f"/api/v1/trainers/{profile_id}/plans", headers=auth(student_token)).json() == []
    own = api.get(PLANS_PATH, headers=auth(trainer_token))
    assert [item["is_active"] for item in own.json()] == [False]


def test_plan_validation_errors_use_problem_details(client):
    api, _ = client
    token = register_and_login(api, "coach@example.com", "TRAINER")

    out_of_range = api.post(PLANS_PATH, headers=auth(token), json={"title": "Premium", "monthly_price": 1500000})
    assert out_of_range.status_code == 422
    assert out_of_range.headers["content-type"].startswith("application/problem+json")
    assert out_of_range.json()["errors"] == [
        {"field": "monthly_price", "message": "La tarifa debe estar entre $0 y $1.000.000"}
    ]

    missing = api.post(PLANS_PATH, headers=auth(token), json={})
    assert missing.status_code == 422
    assert {item["field"]: item["message"] for item in missing.json()["errors"]} == {
        "title": "Este campo es obligatorio",
        "monthly_price": "Este campo es obligatorio",
    }
    assert api.get(PLANS_PATH, headers=auth(token)).json() == []


def test_plans_enforce_role_ownership_and_draft_visibility(client):
    api, _ = client
    trainer_token = register_and_login(api, "coach@example.com", "TRAINER")
    other_token = register_and_login(api, "other@example.com", "TRAINER")
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    assert api.get(PLANS_PATH, headers=auth(student_token)).status_code == 403
    assert api.post(PLANS_PATH, json={"title": "Plan", "monthly_price": 10}).status_code == 401

    plan_id = api.post(PLANS_PATH, headers=auth(trainer_token), json={"title": "Plan", "monthly_price": 10}).json()["id"]
    assert api.put(f"{PLANS_PATH}/{plan_id}", headers=auth(other_token), json={"title": "X"}).status_code == 404
    assert api.post(f"{PLANS_PATH}/{plan_id}/archive", headers=auth(other_token)).status_code == 404

    draft_id = api.get("/api/v1/trainers/me/profile", headers=auth(trainer_token)).json()["id"]
    hidden = api.get(f"/api/v1/trainers/{draft_id}/plans", headers=auth(student_token))
    assert hidden.status_code == 404
    assert hidden.headers["content-type"].startswith("application/problem+json")
