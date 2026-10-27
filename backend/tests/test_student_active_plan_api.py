from backend.src.models.training_relationship import TrainingRelationship

TRAINER_DATA = {
    "full_name": "Esteban Giménez",
    "contact_phone": "+5491122334455",
    "specialty": "Funcional y Readaptación",
}
STUDENT_DATA = {
    "first_name": "Nicolás",
    "last_name": "Ríos",
    "birth_date": "1995-10-12T00:00:00Z",
    "contact_phone": "+5491166778899",
    "fitness_goals": ["resistencia"],
}
HEALTH_QUESTIONNAIRE = {
    "has_heart_condition": False,
    "has_chest_pain_activity": False,
    "has_dizziness_or_balance_loss": False,
    "has_bone_joint_problem": False,
    "takes_prescription_meds": False,
}


def register_and_login(api, email: str, role: str) -> str:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_student_active_plan_empty_when_no_relationship(client):
    api, _ = client
    student_token = register_and_login(api, "student_empty@example.com", "STUDENT")
    api.put("/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_DATA)

    response = api.get("/api/v1/students/me/active-plan", headers=auth(student_token))
    assert response.status_code == 200
    data = response.json()
    assert data["has_active_plan"] is False
    assert data["relationship_id"] is None
    assert data["trainer"] is None


def test_student_active_plans_include_pending_requests(client):
    api, _ = client
    trainer_token = register_and_login(api, "coach_pending@example.com", "TRAINER")
    trainer_prof = api.put(
        "/api/v1/trainers/me/profile", headers=auth(trainer_token), json=TRAINER_DATA
    ).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(trainer_token), json={"max_students": 5})
    plan = api.post(
        "/api/v1/trainers/me/plans",
        headers=auth(trainer_token),
        json={"title": "Plan pendiente", "monthly_price": 18000},
    ).json()

    student_token = register_and_login(api, "student_pending@example.com", "STUDENT")
    api.put("/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_DATA)
    api.post(
        "/api/v1/students/me/health-questionnaire",
        headers=auth(student_token),
        json=HEALTH_QUESTIONNAIRE,
    )
    request = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(student_token),
        json={"trainer_id": trainer_prof["id"], "plan_id": plan["id"]},
    ).json()

    response = api.get("/api/v1/students/me/active-plans", headers=auth(student_token))
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) == 1
    pending = plans[0]
    assert pending["has_active_plan"] is False
    assert pending["status"] == "PENDING"
    assert pending["request_id"] == request["id"]
    assert pending["requested_at"] is not None
    assert pending["trainer"]["id"] == trainer_prof["id"]
    assert pending["plan"]["id"] == plan["id"]
    assert pending["agreed_monthly_price"] == 18000.0
    assert pending["welcome_message"] is None
    assert pending["routine"] is None

    active_plan = api.get("/api/v1/students/me/active-plan", headers=auth(student_token))
    assert active_plan.status_code == 200
    assert active_plan.json()["has_active_plan"] is False


def test_student_active_plan_after_acceptance(client):
    api, _ = client
    # Setup trainer
    trainer_token = register_and_login(api, "coach_esteban@example.com", "TRAINER")
    trainer_prof = api.put(
        "/api/v1/trainers/me/profile", headers=auth(trainer_token), json=TRAINER_DATA
    ).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(trainer_token), json={"max_students": 5})
    plan = api.post(
        "/api/v1/trainers/me/plans",
        headers=auth(trainer_token),
        json={"title": "Funcional Intermedio", "monthly_price": 30000},
    ).json()

    # Setup student
    student_token = register_and_login(api, "student_nico@example.com", "STUDENT")
    api.put("/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_DATA)
    api.post(
        "/api/v1/students/me/health-questionnaire",
        headers=auth(student_token),
        json=HEALTH_QUESTIONNAIRE,
    )

    # Request & Accept
    req = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(student_token),
        json={"trainer_id": trainer_prof["id"], "plan_id": plan["id"]},
    ).json()
    api.post(
        f"/api/v1/matchmaking/requests/{req['id']}/accept",
        headers=auth(trainer_token),
        json={"welcome_message": "¡Hola Nico! Tu plan ya está activo."},
    )

    # Query active plan as student
    response = api.get("/api/v1/students/me/active-plan", headers=auth(student_token))
    assert response.status_code == 200
    data = response.json()
    assert data["has_active_plan"] is True
    assert data["status"] == "ACTIVE"
    assert data["agreed_monthly_price"] == 30000.0
    assert data["agreed_currency"] == "ARS"
    assert data["welcome_message"] == "¡Hola Nico! Tu plan ya está activo."
    assert data["trainer"]["id"] == trainer_prof["id"]
    assert data["trainer"]["full_name"] == "Esteban Giménez"
    assert data["trainer"]["specialty"] == "Funcional y Readaptación"
    assert data["trainer"]["email"] == "coach_esteban@example.com"
    assert data["plan"]["id"] == plan["id"]
    assert data["plan"]["title"] == "Funcional Intermedio"
    assert data["routine"] is None


def test_student_active_plan_with_assigned_routine(client):
    api, session_factory = client
    # Setup trainer & student & accept
    trainer_token = register_and_login(api, "trainer_routine@example.com", "TRAINER")
    t_prof = api.put(
        "/api/v1/trainers/me/profile", headers=auth(trainer_token), json=TRAINER_DATA
    ).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(trainer_token), json={"max_students": 5})
    plan = api.post(
        "/api/v1/trainers/me/plans",
        headers=auth(trainer_token),
        json={"title": "Plan con Rutina", "monthly_price": 25000},
    ).json()

    student_token = register_and_login(api, "student_routine@example.com", "STUDENT")
    s_prof = api.put("/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_DATA).json()
    api.post(
        "/api/v1/students/me/health-questionnaire",
        headers=auth(student_token),
        json=HEALTH_QUESTIONNAIRE,
    )
    req = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(student_token),
        json={"trainer_id": t_prof["id"], "plan_id": plan["id"]},
    ).json()
    api.post(
        f"/api/v1/matchmaking/requests/{req['id']}/accept",
        headers=auth(trainer_token),
        json={},
    )

    # Simulate trainer assigning a routine to the relationship
    with session_factory() as db:
        rel = db.query(TrainingRelationship).filter_by(student_id=s_prof["id"]).first()
        rel.initial_routine_id = "routine-uuid-1234"
        db.commit()

    # Query active plan as student
    response = api.get("/api/v1/students/me/active-plan", headers=auth(student_token))
    assert response.status_code == 200
    data = response.json()
    assert data["has_active_plan"] is True
    assert data["routine"] is not None
    assert data["routine"]["id"] == "routine-uuid-1234"
    assert data["routine"]["is_available"] is True


def test_trainer_cannot_query_student_active_plan(client):
    api, _ = client
    trainer_token = register_and_login(api, "only_trainer@example.com", "TRAINER")
    response = api.get("/api/v1/students/me/active-plan", headers=auth(trainer_token))
    assert response.status_code == 403


def test_student_multiple_active_plans(client):
    api, _ = client
    # Setup trainer 1
    t1_token = register_and_login(api, "coach1@example.com", "TRAINER")
    t1_prof = api.put(
        "/api/v1/trainers/me/profile", headers=auth(t1_token), json={**TRAINER_DATA, "full_name": "Coach Uno"}
    ).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(t1_token), json={"max_students": 5})
    plan1 = api.post(
        "/api/v1/trainers/me/plans", headers=auth(t1_token), json={"title": "Plan Uno", "monthly_price": 20000}
    ).json()

    # Setup trainer 2
    t2_token = register_and_login(api, "coach2@example.com", "TRAINER")
    t2_prof = api.put(
        "/api/v1/trainers/me/profile", headers=auth(t2_token), json={**TRAINER_DATA, "full_name": "Coach Dos"}
    ).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(t2_token), json={"max_students": 5})
    plan2 = api.post(
        "/api/v1/trainers/me/plans", headers=auth(t2_token), json={"title": "Plan Dos", "monthly_price": 25000}
    ).json()

    # Setup student
    student_token = register_and_login(api, "student_multi@example.com", "STUDENT")
    api.put("/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_DATA)
    api.post("/api/v1/students/me/health-questionnaire", headers=auth(student_token), json=HEALTH_QUESTIONNAIRE)

    # Request & Accept both
    req1 = api.post("/api/v1/matchmaking/requests", headers=auth(student_token), json={"trainer_id": t1_prof["id"], "plan_id": plan1["id"]}).json()
    api.post(f"/api/v1/matchmaking/requests/{req1['id']}/accept", headers=auth(t1_token), json={"welcome_message": "Bienvenido a Plan 1"})

    req2 = api.post("/api/v1/matchmaking/requests", headers=auth(student_token), json={"trainer_id": t2_prof["id"], "plan_id": plan2["id"]}).json()
    api.post(f"/api/v1/matchmaking/requests/{req2['id']}/accept", headers=auth(t2_token), json={"welcome_message": "Bienvenido a Plan 2"})

    # Query active-plans
    resp = api.get("/api/v1/students/me/active-plans", headers=auth(student_token))
    assert resp.status_code == 200
    plans = resp.json()
    assert isinstance(plans, list)
    assert len(plans) == 2
    trainer_names = {p["trainer"]["full_name"] for p in plans}
    assert trainer_names == {"Coach Uno", "Coach Dos"}


def test_unauthenticated_active_plan(client):
    api, _ = client
    response = api.get("/api/v1/students/me/active-plan")
    assert response.status_code == 401
