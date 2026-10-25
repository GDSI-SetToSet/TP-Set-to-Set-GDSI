from backend.src.models.notification import Notification
from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.services.notification_service import create_notification
from sqlalchemy import select

TRAINER_PUBLISHED = {
    "full_name": "Marcos Entrenador",
    "contact_phone": "+5491155551234",
    "specialty": "Fuerza y Rendimiento",
}
STUDENT_PROFILE = {
    "first_name": "Camila",
    "last_name": "López",
    "birth_date": "1998-05-20T00:00:00Z",
    "contact_phone": "+5491199887766",
    "fitness_goals": ["fuerza", "hipertrofia"],
    "personal_motivation": "Entrenar para correr media maratón",
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


def setup_trainer_and_student(api):
    trainer_token = register_and_login(api, "trainer_us49@example.com", "TRAINER")
    trainer_prof = api.put(
        "/api/v1/trainers/me/profile", headers=auth(trainer_token), json=TRAINER_PUBLISHED
    ).json()
    api.patch("/api/v1/trainers/me/quota", headers=auth(trainer_token), json={"max_students": 5})
    plan_resp = api.post(
        "/api/v1/trainers/me/plans",
        headers=auth(trainer_token),
        json={"title": "Plan Pro Fuerza", "monthly_price": 28000},
    )
    plan_id = plan_resp.json()["id"]

    student_token = register_and_login(api, "student_us49@example.com", "STUDENT")
    student_prof = api.put(
        "/api/v1/students/me/profile", headers=auth(student_token), json=STUDENT_PROFILE
    ).json()
    api.post(
        "/api/v1/students/me/health-questionnaire",
        headers=auth(student_token),
        json=HEALTH_QUESTIONNAIRE,
    )
    return trainer_token, trainer_prof["id"], plan_id, student_token, student_prof["id"]


def test_accept_request_emits_welcome_notification_with_custom_message(client):
    api, session_factory = client
    t_tok, t_id, plan_id, s_tok, s_id = setup_trainer_and_student(api)

    # Student sends request
    req = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(s_tok),
        json={"trainer_id": t_id, "plan_id": plan_id, "student_message": "Hola Marcos!"},
    ).json()
    req_id = req["id"]

    # Trainer accepts with custom welcome message
    custom_msg = "¡Bienvenida Camila! Mañana comenzamos con la evaluación inicial."
    accept_resp = api.post(
        f"/api/v1/matchmaking/requests/{req_id}/accept",
        headers=auth(t_tok),
        json={"welcome_message": custom_msg},
    )
    assert accept_resp.status_code == 200

    # Verify TrainingRelationship persistence
    with session_factory() as db:
        rel = db.scalar(select(TrainingRelationship).where(TrainingRelationship.student_id == s_id))
        assert rel is not None
        assert rel.status == "ACTIVE"
        assert rel.welcome_message == custom_msg
        assert rel.welcome_message_sent is True
        assert rel.initial_routine_id is None

        # Verify Notification emitted to student's user_id
        student_user_id = db.scalar(select(StudentProfile.user_id).where(StudentProfile.id == s_id))
        notifs = db.scalars(
            select(Notification).where(Notification.recipient_id == student_user_id)
        ).all()
        assert len(notifs) == 1
        notif = notifs[0]
        assert notif.type == "TRAINING_ACCEPTED"
        assert notif.title == "¡Bienvenido/a al programa de entrenamiento!"
        assert notif.message == custom_msg
        assert notif.related_entity_type == "TrainingRelationship"
        assert notif.related_entity_id == rel.id
        assert notif.is_read is False


def test_accept_request_emits_welcome_notification_with_default_fallback(client):
    api, session_factory = client
    t_tok, t_id, plan_id, s_tok, s_id = setup_trainer_and_student(api)

    req = api.post(
        "/api/v1/matchmaking/requests",
        headers=auth(s_tok),
        json={"trainer_id": t_id, "plan_id": plan_id},
    ).json()

    # Trainer accepts without custom message
    accept_resp = api.post(
        f"/api/v1/matchmaking/requests/{req['id']}/accept",
        headers=auth(t_tok),
        json={},
    )
    assert accept_resp.status_code == 200

    with session_factory() as db:
        student_user_id = db.scalar(select(StudentProfile.user_id).where(StudentProfile.id == s_id))
        notif = db.scalar(
            select(Notification).where(Notification.recipient_id == student_user_id)
        )
        assert notif is not None
        assert "Marcos Entrenador" in notif.message
        assert "Plan Pro Fuerza" in notif.message
        assert notif.is_read is False


def test_notification_service_create_and_query(client):
    _, session_factory = client
    with session_factory() as db:
        notif = create_notification(
            db=db,
            recipient_id="fake-user-id",
            type="GENERAL",
            title="Aviso",
            message="Mensaje de prueba",
            commit=True,
        )
        assert notif.id is not None
        assert notif.title == "Aviso"
        assert notif.is_read is False
