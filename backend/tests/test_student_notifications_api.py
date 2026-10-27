from backend.src.models.notification import Notification
from backend.src.models.user import User
from backend.src.services.notification_service import create_notification


def register_and_login(api, email: str, role: str) -> str:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_notifications_and_unread_count(client):
    api, session_factory = client
    student_token = register_and_login(api, "student_notif@example.com", "STUDENT")

    with session_factory() as db:
        user = db.query(User).filter_by(email="student_notif@example.com").first()
        create_notification(
            db, user.id, "TRAINING_ACCEPTED", "Bienvenido", "Mensaje 1", commit=True
        )
        create_notification(
            db, user.id, "ROUTINE_ASSIGNED", "Nueva Rutina", "Mensaje 2", commit=True
        )

    response = api.get("/api/v1/students/me/notifications", headers=auth(student_token))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["unread_count"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Nueva Rutina"
    assert data["items"][1]["title"] == "Bienvenido"


def test_filter_notifications_by_is_read(client):
    api, session_factory = client
    student_token = register_and_login(api, "student_filter@example.com", "STUDENT")

    with session_factory() as db:
        user = db.query(User).filter_by(email="student_filter@example.com").first()
        n1 = create_notification(db, user.id, "TYPE1", "Title 1", "Msg 1", commit=False)
        n1.is_read = True
        create_notification(db, user.id, "TYPE2", "Title 2", "Msg 2", commit=False)
        db.commit()

    # Filter unread
    resp_unread = api.get(
        "/api/v1/students/me/notifications?is_read=false", headers=auth(student_token)
    )
    assert resp_unread.status_code == 200
    assert resp_unread.json()["total"] == 1
    assert resp_unread.json()["unread_count"] == 1
    assert resp_unread.json()["items"][0]["title"] == "Title 2"

    # Filter read
    resp_read = api.get(
        "/api/v1/students/me/notifications?is_read=true", headers=auth(student_token)
    )
    assert resp_read.status_code == 200
    assert resp_read.json()["total"] == 1
    assert resp_read.json()["items"][0]["title"] == "Title 1"


def test_mark_notification_as_read(client):
    api, session_factory = client
    student_token = register_and_login(api, "student_read@example.com", "STUDENT")

    with session_factory() as db:
        user = db.query(User).filter_by(email="student_read@example.com").first()
        notif = create_notification(
            db, user.id, "TRAINING_ACCEPTED", "Aviso", "Texto", commit=True
        )
        notif_id = notif.id

    patch_resp = api.patch(
        f"/api/v1/students/me/notifications/{notif_id}/read", headers=auth(student_token)
    )
    assert patch_resp.status_code == 200
    item = patch_resp.json()
    assert item["is_read"] is True
    assert item["read_at"] is not None

    # Check unread count is now 0
    list_resp = api.get("/api/v1/students/me/notifications", headers=auth(student_token))
    assert list_resp.json()["unread_count"] == 0


def test_mark_notification_of_another_user_forbidden(client):
    api, session_factory = client
    register_and_login(api, "user1@example.com", "STUDENT")
    user2_token = register_and_login(api, "user2@example.com", "STUDENT")

    with session_factory() as db:
        u1 = db.query(User).filter_by(email="user1@example.com").first()
        notif = create_notification(db, u1.id, "NOTICE", "Para User 1", "Privado", commit=True)
        notif_id = notif.id

    # User 2 tries to mark User 1's notification as read
    resp = api.patch(
        f"/api/v1/students/me/notifications/{notif_id}/read", headers=auth(user2_token)
    )
    assert resp.status_code == 403


def test_mark_nonexistent_notification_not_found(client):
    api, _ = client
    student_token = register_and_login(api, "student_404@example.com", "STUDENT")
    resp = api.patch(
        "/api/v1/students/me/notifications/non-existent-id/read", headers=auth(student_token)
    )
    assert resp.status_code == 404


def test_trainer_cannot_access_or_mark_student_notifications(client):
    api, _ = client
    trainer_token = register_and_login(api, "trainer_notif@example.com", "TRAINER")

    list_resp = api.get("/api/v1/students/me/notifications", headers=auth(trainer_token))
    assert list_resp.status_code == 403
    assert "alumnos" in list_resp.json()["detail"].lower()

    patch_resp = api.patch(
        "/api/v1/students/me/notifications/some-id/read", headers=auth(trainer_token)
    )
    assert patch_resp.status_code == 403
    assert "alumnos" in patch_resp.json()["detail"].lower()


def test_trainer_notifications_rbac_isolation_and_no_db_mutation_on_denied(client):
    api, session_factory = client
    trainer1_token = register_and_login(api, "trainer1_notif@example.com", "TRAINER")
    trainer2_token = register_and_login(api, "trainer2_notif@example.com", "TRAINER")
    student_token = register_and_login(api, "student_for_trainer_notif@example.com", "STUDENT")

    with session_factory() as db:
        t1 = db.query(User).filter_by(email="trainer1_notif@example.com").first()
        notif = create_notification(
            db,
            t1.id,
            "NEW_REQUEST",
            "¡Nueva solicitud de entrenamiento!",
            "El alumno solicitó unirse a tu plan.",
            commit=True,
        )
        notif_id = notif.id

    # 1. Student cannot access trainer notification endpoints (403)
    student_list = api.get("/api/v1/trainers/me/notifications", headers=auth(student_token))
    assert student_list.status_code == 403
    assert "entrenadores" in student_list.json()["detail"].lower()

    student_patch = api.patch(
        f"/api/v1/trainers/me/notifications/{notif_id}/read", headers=auth(student_token)
    )
    assert student_patch.status_code == 403
    assert "entrenadores" in student_patch.json()["detail"].lower()

    # 2. Trainer 2 cannot see or mark Trainer 1's notification
    t2_list = api.get("/api/v1/trainers/me/notifications", headers=auth(trainer2_token))
    assert t2_list.status_code == 200
    assert t2_list.json()["total"] == 0

    t2_patch = api.patch(
        f"/api/v1/trainers/me/notifications/{notif_id}/read", headers=auth(trainer2_token)
    )
    assert t2_patch.status_code == 403

    # 3. Verify no DB mutation occurred after denied attempts
    with session_factory() as db:
        persisted = db.get(Notification, notif_id)
        assert persisted.is_read is False
        assert persisted.read_at is None

    # 4. Trainer 1 (owner) can list and mark as read
    t1_list = api.get("/api/v1/trainers/me/notifications", headers=auth(trainer1_token))
    assert t1_list.status_code == 200
    assert t1_list.json()["total"] == 1
    assert t1_list.json()["unread_count"] == 1
    assert t1_list.json()["items"][0]["type"] == "NEW_REQUEST"

    t1_patch = api.patch(
        f"/api/v1/trainers/me/notifications/{notif_id}/read", headers=auth(trainer1_token)
    )
    assert t1_patch.status_code == 200
    assert t1_patch.json()["is_read"] is True
    assert t1_patch.json()["read_at"] is not None


def test_unauthenticated_notifications(client):
    api, _ = client
    assert api.get("/api/v1/students/me/notifications").status_code == 401
    assert api.patch("/api/v1/students/me/notifications/some-id/read").status_code == 401
    assert api.get("/api/v1/trainers/me/notifications").status_code == 401
    assert api.patch("/api/v1/trainers/me/notifications/some-id/read").status_code == 401
