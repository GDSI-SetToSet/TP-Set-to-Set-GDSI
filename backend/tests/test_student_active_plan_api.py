from datetime import UTC, date, datetime, timedelta, timezone

from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.training_request import TrainingRequest
from backend.src.schemas.discovery import ActivePlanResponse
from backend.src.services.discovery_service import _item_sort_datetime

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
    assert pending["trainer"]["full_name"] == TRAINER_DATA["full_name"]
    assert pending["trainer"]["specialty"] == TRAINER_DATA["specialty"]
    # H-03 / Paso 3: trainer private email and phone must not be exposed while PENDING
    assert pending["trainer"]["email"] is None
    assert pending["trainer"]["phone"] is None
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
    assert data["trainer"]["phone"] == "+5491122334455"
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
    list_response = api.get("/api/v1/students/me/active-plans", headers=auth(trainer_token))
    assert list_response.status_code == 403


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


def test_student_active_plans_sorting_mixed_naive_and_aware_datetimes_and_transitions(client):
    api, session_factory = client

    # Setup 3 trainers
    trainers = []
    for idx in range(1, 4):
        tok = register_and_login(api, f"coach_sort_{idx}@example.com", "TRAINER")
        prof = api.put(
            "/api/v1/trainers/me/profile",
            headers=auth(tok),
            json={**TRAINER_DATA, "full_name": f"Coach {idx}", "contact_phone": f"+549110000000{idx}"},
        ).json()
        api.patch("/api/v1/trainers/me/quota", headers=auth(tok), json={"max_students": 5})
        pl = api.post(
            "/api/v1/trainers/me/plans",
            headers=auth(tok),
            json={"title": f"Plan {idx}", "monthly_price": 10000 * idx},
        ).json()
        trainers.append((tok, prof["id"], pl["id"]))

    student_token = register_and_login(api, "student_sort@example.com", "STUDENT")
    api.put("/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_DATA)
    api.post(
        "/api/v1/students/me/health-questionnaire",
        headers=auth(student_token),
        json=HEALTH_QUESTIONNAIRE,
    )

    # Create 3 requests: accept #1 (ACTIVE), leave #2 and #3 PENDING
    req1 = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(student_token),
        json={"trainer_id": trainers[0][1], "plan_id": trainers[0][2]},
    ).json()
    rel1 = api.post(
        f"/api/v1/matchmaking/requests/{req1['id']}/accept",
        headers=auth(trainers[0][0]),
        json={"welcome_message": "Activo"},
    ).json()

    req2 = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(student_token),
        json={"trainer_id": trainers[1][1], "plan_id": trainers[1][2]},
    ).json()
    req3 = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(student_token),
        json={"trainer_id": trainers[2][1], "plan_id": trainers[2][2]},
    ).json()

    # Set distinct dates in DB and test mixed naive/aware sorting
    with session_factory() as db:
        r_active = db.get(TrainingRelationship, rel1["id"])
        r_active.start_date = date(2026, 10, 20)

        r_pend_old = db.get(TrainingRequest, req2["id"])
        r_pend_old.created_at = datetime(2026, 10, 15, 10, 0, 0)  # naive UTC older than start_date

        r_pend_new = db.get(TrainingRequest, req3["id"])
        r_pend_new.created_at = datetime(2026, 10, 25, 14, 30, 0, tzinfo=UTC)  # aware UTC newer than start_date
        db.commit()

    resp = api.get("/api/v1/students/me/active-plans", headers=auth(student_token))
    assert resp.status_code == 200
    items = resp.json()
    assert [item["status"] for item in items] == ["PENDING", "ACTIVE", "PENDING"]
    assert items[0]["request_id"] == req3["id"]
    assert items[0]["trainer"]["email"] is None
    assert items[0]["trainer"]["phone"] is None

    assert items[1]["relationship_id"] == rel1["id"]
    assert items[1]["has_active_plan"] is True
    assert items[1]["trainer"]["email"] == "coach_sort_1@example.com"
    assert items[1]["trainer"]["phone"] == "+5491100000001"

    assert items[2]["request_id"] == req2["id"]
    assert items[2]["trainer"]["email"] is None
    assert items[2]["trainer"]["phone"] is None

    # /active-plan must still return the ACTIVE relationship even though a PENDING request is newer
    single_active = api.get("/api/v1/students/me/active-plan", headers=auth(student_token)).json()
    assert single_active["has_active_plan"] is True
    assert single_active["relationship_id"] == rel1["id"]

    # Unit check on _item_sort_datetime with naive UTC, aware UTC, and non-UTC offset (-03:00)
    ar_tz = timezone(timedelta(hours=-3))
    item_naive = ActivePlanResponse(
        has_active_plan=False,
        status="PENDING",
        requested_at=datetime(2026, 10, 26, 12, 0, 0),  # 12:00 UTC
    )
    item_aware_utc = ActivePlanResponse(
        has_active_plan=False,
        status="PENDING",
        requested_at=datetime(2026, 10, 26, 13, 0, 0, tzinfo=UTC),  # 13:00 UTC
    )
    item_aware_ar = ActivePlanResponse(
        has_active_plan=False,
        status="PENDING",
        requested_at=datetime(2026, 10, 26, 11, 0, 0, tzinfo=ar_tz),  # 14:00 UTC
    )
    item_start_date = ActivePlanResponse(
        has_active_plan=True,
        status="ACTIVE",
        start_date=date(2026, 10, 26),  # 00:00 UTC
    )
    sorted_items = sorted(
        [item_start_date, item_naive, item_aware_utc, item_aware_ar],
        key=_item_sort_datetime,
        reverse=True,
    )
    assert sorted_items == [item_aware_ar, item_aware_utc, item_naive, item_start_date]

    # Transition ACTIVE relationship to TERMINATED and EXPIRED -> no longer returned as active plan
    for inactive_status in ("TERMINATED", "EXPIRED"):
        with session_factory() as db:
            r_active = db.get(TrainingRelationship, rel1["id"])
            r_active.status = inactive_status
            db.commit()

        after_inactive = api.get("/api/v1/students/me/active-plans", headers=auth(student_token)).json()
        assert all(i["status"] == "PENDING" for i in after_inactive)
        assert len(after_inactive) == 2
        single_after = api.get("/api/v1/students/me/active-plan", headers=auth(student_token)).json()
        assert single_after["has_active_plan"] is False


def test_unauthenticated_active_plan(client):
    api, _ = client
    response = api.get("/api/v1/students/me/active-plan")
    assert response.status_code == 401
