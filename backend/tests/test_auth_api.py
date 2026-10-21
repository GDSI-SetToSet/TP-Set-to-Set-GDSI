from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from backend.src.core.constants import PASSWORD_REQUIREMENTS_MESSAGE
from backend.src.models.user import User


def register(client, email="coach@example.com", role="TRAINER", password="StrongPass123"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password, "role": role})


def test_register_trainer_and_student(client):
    api, _ = client
    trainer = register(api)
    student = register(api, "student@example.com", "STUDENT")
    assert trainer.status_code == 201
    assert trainer.json()["role"] == "TRAINER"
    assert student.status_code == 201
    assert student.json()["role"] == "STUDENT"
    assert "password" not in trainer.json()
    assert "password_hash" not in trainer.json()


def test_register_normalizes_email_and_rejects_duplicate(client):
    api, _ = client
    assert register(api, " Coach@Example.com ").status_code == 201
    duplicate = register(api, "coach@example.com", "STUDENT")
    assert duplicate.status_code == 409


def test_register_rejects_weak_password(client):
    api, _ = client
    response = register(api, password="weak")
    assert response.status_code == 400
    assert response.json()["detail"] == PASSWORD_REQUIREMENTS_MESSAGE


def test_register_rejects_password_missing_character_classes(client):
    api, _ = client
    cases = ["lowercase123", "UPPERCASE123", "NoDigitsHere"]
    for index, password in enumerate(cases):
        response = register(api, f"weak{index}@example.com", password=password)
        assert response.status_code == 400
        assert response.json()["detail"] == PASSWORD_REQUIREMENTS_MESSAGE


def test_register_uses_same_message_for_empty_and_overlong_password(client):
    api, _ = client
    for index, password in enumerate(("", "A" * 129)):
        response = register(api, f"length{index}@example.com", password=password)
        assert response.status_code == 400
        assert response.json()["detail"] == PASSWORD_REQUIREMENTS_MESSAGE


def test_register_rejects_invalid_email_and_role(client):
    api, _ = client
    invalid_email = api.post("/api/v1/auth/register", json={"email": "nope", "password": "StrongPass123", "role": "TRAINER"})
    invalid_role = api.post("/api/v1/auth/register", json={"email": "role@example.com", "password": "StrongPass123", "role": "ADMIN"})
    assert invalid_email.status_code == 422
    assert invalid_role.status_code == 422


def test_login_returns_role_and_persistent_token(client):
    api, _ = client
    register(api, role="TRAINER")
    response = api.post("/api/v1/auth/login", json={"email": "COACH@example.com", "password": "StrongPass123"})
    body = response.json()
    assert response.status_code == 200
    assert body["user"]["role"] == "TRAINER"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 24 * 60 * 60
    assert api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()["email"] == "coach@example.com"


def test_invalid_login_uses_generic_message_and_lockout(client):
    api, sessions = client
    register(api)
    for attempt in range(5):
        response = api.post("/api/v1/auth/login", json={"email": "coach@example.com", "password": "WrongPass123"})
        if attempt < 4:
            assert response.status_code == 401
            assert response.json()["detail"] == "Mail o contraseña incorrectos"
        else:
            assert response.status_code == 423
            assert response.json()["detail"] == "Se excedió el límite de intentos. Volvé a intentar en 15 minutos."
            assert response.headers["retry-after"] == "900"
    locked = api.post("/api/v1/auth/login", json={"email": "coach@example.com", "password": "StrongPass123"})
    assert locked.status_code == 423
    assert 1 <= int(locked.headers["retry-after"]) <= 900
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == "coach@example.com"))
        assert user.failed_login_attempts == 5
        assert user.locked_until is not None


def test_expired_lockout_resets_and_correct_login_succeeds(client):
    api, sessions = client
    register(api)
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == "coach@example.com"))
        user.failed_login_attempts = 5
        user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    response = api.post("/api/v1/auth/login", json={"email": "coach@example.com", "password": "StrongPass123"})
    assert response.status_code == 200
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == "coach@example.com"))
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


def test_unknown_email_and_inactive_account_are_generic(client):
    api, sessions = client
    assert api.post("/api/v1/auth/login", json={"email": "missing@example.com", "password": "WrongPass123"}).json()["detail"] == "Mail o contraseña incorrectos"
    malformed_email = api.post("/api/v1/auth/login", json={"email": "martina", "password": "WrongPass123"})
    assert malformed_email.status_code == 401
    assert malformed_email.json()["detail"] == "Mail o contraseña incorrectos"
    register(api)
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == "coach@example.com"))
        user.is_active = False
        db.commit()
    response = api.post("/api/v1/auth/login", json={"email": "coach@example.com", "password": "StrongPass123"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Mail o contraseña incorrectos"


def test_me_requires_session_and_logout_revokes_it(client, registered_user):
    api, _ = client
    assert api.get("/api/v1/auth/me").status_code == 401
    login = api.post("/api/v1/auth/login", json={"email": "alumna@example.com", "password": "StrongPass123"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert api.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert api.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_invalid_token_is_rejected(client):
    api, _ = client
    response = api.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_health_endpoint(client):
    api, _ = client
    assert api.get("/health").json() == {"status": "ok"}
