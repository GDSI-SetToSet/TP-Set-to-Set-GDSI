SEARCH_PATH = "/api/v1/trainers/search"
PUBLIC_PATH = "/api/v1/trainers/{}/public"
REQUEST_PATH = "/api/v1/matchmaking/requests"
MY_REQUESTS_PATH = "/api/v1/matchmaking/requests/mine"

TRAINER_PUBLISHED = {"full_name": "Lucas Pérez", "contact_phone": "+5491155551234", "specialty": "Fuerza"}
STUDENT_PROFILE = {
    "first_name": "María",
    "last_name": "García",
    "birth_date": "2000-01-15T00:00:00",
    "contact_phone": "+5491100001111",
    "fitness_goals": ["fuerza"],
}
HEALTH_QUESTIONNAIRE = {
    "has_heart_condition": False,
    "has_chest_pain_activity": False,
    "has_dizziness_or_balance_loss": False,
    "has_bone_joint_problem": False,
    "takes_prescription_meds": False,
    "other_medical_conditions": None,
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
    """Create a published trainer with quota. Returns (token, profile_id)."""
    token = register_and_login(api, email, "TRAINER")
    body = {**TRAINER_PUBLISHED, "full_name": full_name}
    profile = api.put("/api/v1/trainers/me/profile", headers=auth(token), json=body).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(token), json={"max_students": max_students})
    return token, profile["id"]


def setup_student_with_health(api, email: str) -> str:
    """Create a student with profile + health questionnaire. Returns token."""
    token = register_and_login(api, email, "STUDENT")
    api.put("/api/v1/students/me/profile", headers=auth(token), json=STUDENT_PROFILE)
    api.post("/api/v1/students/me/health-questionnaire", headers=auth(token), json=HEALTH_QUESTIONNAIRE)
    return token


def create_plan(api, trainer_token: str, title: str = "Plan Fuerza", price: int = 25000) -> str:
    resp = api.post(
        "/api/v1/trainers/me/plans",
        headers=auth(trainer_token),
        json={"title": title, "monthly_price": price},
    )
    return resp.json()["id"]


# ── Search tests ──


def test_search_returns_published_trainers_with_active_plans(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com")
    create_plan(api, trainer_token)
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    resp = api.get(SEARCH_PATH, headers=auth(student_token), params={"only_available": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(t["id"] == profile_id for t in data["items"])


def test_search_filters_by_specialty(client):
    api, _ = client
    trainer_token, _ = setup_published_trainer(api, "coach@example.com")
    create_plan(api, trainer_token)
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    found = api.get(SEARCH_PATH, headers=auth(student_token), params={"specialty": "fuerza", "only_available": False})
    assert found.status_code == 200
    assert found.json()["total"] >= 1

    not_found = api.get(SEARCH_PATH, headers=auth(student_token), params={"specialty": "yoga", "only_available": False})
    assert not_found.status_code == 200
    assert not_found.json()["total"] == 0


def test_search_filters_by_max_price(client):
    api, _ = client
    trainer_token, _ = setup_published_trainer(api, "coach@example.com")
    create_plan(api, trainer_token, price=30000)
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    cheap = api.get(SEARCH_PATH, headers=auth(student_token), params={"max_price": 10000, "only_available": False})
    assert cheap.status_code == 200
    assert cheap.json()["total"] == 0

    enough = api.get(SEARCH_PATH, headers=auth(student_token), params={"max_price": 30000, "only_available": False})
    assert enough.status_code == 200
    assert enough.json()["total"] >= 1


def test_search_draft_trainer_not_visible(client):
    api, _ = client
    # Create trainer but don't publish (incomplete profile)
    trainer_token = register_and_login(api, "draft@example.com", "TRAINER")
    api.put("/api/v1/trainers/me/profile", headers=auth(trainer_token), json={"full_name": "Draft Coach"})
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    resp = api.get(SEARCH_PATH, headers=auth(student_token), params={"only_available": False})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_search_pagination_counts_only_available_trainers(client):
    api, _ = client
    # "Ana" sorts first but has no quota: with the default only_available filter she must not
    # take up a slot in the page nor in the total.
    no_quota_token, _ = setup_published_trainer(api, "ana@example.com", max_students=0, full_name="Ana Sin Cupo")
    create_plan(api, no_quota_token)
    quota_token, quota_id = setup_published_trainer(api, "zoe@example.com", max_students=3, full_name="Zoe Con Cupo")
    create_plan(api, quota_token)
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    resp = api.get(SEARCH_PATH, headers=auth(student_token), params={"page_size": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert [t["id"] for t in data["items"]] == [quota_id]

    page_two = api.get(SEARCH_PATH, headers=auth(student_token), params={"page_size": 1, "page": 2}).json()
    assert page_two["total"] == 1
    assert page_two["items"] == []

    everyone = api.get(SEARCH_PATH, headers=auth(student_token), params={"only_available": False}).json()
    assert everyone["total"] == 2


def test_search_requires_authentication(client):
    api, _ = client
    resp = api.get(SEARCH_PATH)
    assert resp.status_code == 401


# ── Public detail tests ──


def test_public_detail_with_plans_and_quota(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com", max_students=3)
    plan_id = create_plan(api, trainer_token, "Premium", 50000)
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    resp = api.get(PUBLIC_PATH.format(profile_id), headers=auth(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Lucas Pérez"
    assert data["available_slots"] == 3
    assert data["has_available_quota"] is True
    assert len(data["plans"]) == 1
    assert data["plans"][0]["id"] == plan_id
    assert data["plans"][0]["monthly_price"] == 50000


def test_public_detail_draft_returns_404(client):
    api, _ = client
    trainer_token = register_and_login(api, "draft@example.com", "TRAINER")
    profile_id = api.get("/api/v1/trainers/me/profile", headers=auth(trainer_token)).json()["id"]
    student_token = register_and_login(api, "student@example.com", "STUDENT")

    resp = api.get(PUBLIC_PATH.format(profile_id), headers=auth(student_token))
    assert resp.status_code == 404


# ── Training request tests (US-48) ──


def test_student_sends_request_successfully(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token, "Plan Básico", 20000)
    student_token = setup_student_with_health(api, "student@example.com")

    resp = api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": plan_id, "student_message": "Hola, quiero entrenar"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["trainer_id"] == profile_id
    assert data["plan_id"] == plan_id
    assert data["student_message"] == "Hola, quiero entrenar"
    assert data["agreed_monthly_price"] == 20000
    assert data["agreed_currency"] == "ARS"

    notifications = api.get(
        "/api/v1/students/me/notifications",
        headers=auth(trainer_token),
    )
    assert notifications.status_code == 200
    notification = notifications.json()["items"][0]
    assert notification["type"] == "NEW_TRAINING_REQUEST"
    assert notification["title"] == "¡Nueva solicitud de entrenamiento!"
    assert notification["message"] == (
        "El alumno María García ha solicitado unirse a tu plan Plan Básico."
    )
    assert notification["related_entity_type"] == "TrainingRequest"
    assert notification["related_entity_id"] == data["id"]


def test_student_without_health_questionnaire_cannot_request(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)
    # Student with profile but no health questionnaire
    student_token = register_and_login(api, "student@example.com", "STUDENT")
    api.put("/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_PROFILE)

    resp = api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": plan_id},
    )
    assert resp.status_code == 403
    assert "cuestionario" in resp.json()["detail"].lower()


def test_request_nonexistent_plan_returns_404(client):
    api, _ = client
    _, profile_id = setup_published_trainer(api, "coach@example.com")
    student_token = setup_student_with_health(api, "student@example.com")

    resp = api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": "nonexistent-plan-id"},
    )
    assert resp.status_code == 404


def test_request_inactive_plan_returns_404(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)
    # Archive the plan
    api.post(f"/api/v1/trainers/me/plans/{plan_id}/archive", headers=auth(trainer_token))
    student_token = setup_student_with_health(api, "student@example.com")

    resp = api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": plan_id},
    )
    assert resp.status_code == 404


def test_trainer_without_quota_returns_409(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com", max_students=0)
    plan_id = create_plan(api, trainer_token)
    student_token = setup_student_with_health(api, "student@example.com")

    resp = api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": plan_id},
    )
    assert resp.status_code == 409
    assert "cupos" in resp.json()["detail"].lower()


def test_duplicate_pending_request_returns_409(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)
    student_token = setup_student_with_health(api, "student@example.com")

    first = api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": plan_id},
    )
    assert first.status_code == 201

    second = api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": plan_id},
    )
    assert second.status_code == 409
    assert "pendiente" in second.json()["detail"].lower()


def test_trainer_cannot_send_request(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)
    other_trainer_token = register_and_login(api, "other@example.com", "TRAINER")

    resp = api.post(
        REQUEST_PATH,
        headers=auth(other_trainer_token),
        json={"trainer_id": profile_id, "plan_id": plan_id},
    )
    assert resp.status_code == 403


def test_unauthenticated_cannot_send_request(client):
    api, _ = client
    resp = api.post(REQUEST_PATH, json={"trainer_id": "x", "plan_id": "y"})
    assert resp.status_code == 401


def test_student_can_list_own_requests(client):
    api, _ = client
    trainer_token, profile_id = setup_published_trainer(api, "coach@example.com")
    plan_id = create_plan(api, trainer_token)
    student_token = setup_student_with_health(api, "student@example.com")

    api.post(
        REQUEST_PATH,
        headers=auth(student_token),
        json={"trainer_id": profile_id, "plan_id": plan_id, "student_message": "Hola"},
    )

    resp = api.get(MY_REQUESTS_PATH, headers=auth(student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "PENDING"


def test_list_requests_empty_for_new_student(client):
    api, _ = client
    student_token = register_and_login(api, "new@example.com", "STUDENT")

    resp = api.get(MY_REQUESTS_PATH, headers=auth(student_token))
    assert resp.status_code == 200
    assert resp.json() == []
