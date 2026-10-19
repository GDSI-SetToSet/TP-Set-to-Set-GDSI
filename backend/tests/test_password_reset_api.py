from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from backend.src.api.v1.deps import get_email_sender
from backend.src.core.config import PASSWORD_RESET_URL
from backend.src.core.constants import (
    INVALID_RESET_TOKEN_MESSAGE,
    PASSWORD_REQUIREMENTS_MESSAGE,
    PASSWORD_RESET_REQUESTED_MESSAGE,
    PASSWORD_RESET_SUCCESS_MESSAGE,
)
from backend.src.models.user import PasswordResetToken, User

EMAIL = "alumna@example.com"
OLD_PASSWORD = "StrongPass123"
NEW_PASSWORD = "NuevaClave2026"


class FakeEmailSender:
    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


@pytest.fixture
def mailbox(client):
    api, _ = client
    sender = FakeEmailSender()
    api.app.dependency_overrides[get_email_sender] = lambda: sender
    return sender


def forgot(api, email=EMAIL):
    return api.post("/api/v1/auth/forgot-password", json={"email": email})


def reset(api, token, password=NEW_PASSWORD):
    return api.post("/api/v1/auth/reset-password", json={"token": token, "new_password": password})


def login(api, password, email=EMAIL):
    return api.post("/api/v1/auth/login", json={"email": email, "password": password})


def token_from(body: str) -> str:
    link = next(word for word in body.split() if word.startswith(PASSWORD_RESET_URL))
    return parse_qs(urlparse(link).query)["token"][0]


def request_token(api, mailbox, email=EMAIL) -> str:
    assert forgot(api, email).status_code == 200
    return token_from(mailbox.sent[-1][2])


def test_registered_email_receives_reset_link(client, registered_user, mailbox):
    api, _ = client
    response = forgot(api)
    assert response.status_code == 200
    assert response.json()["message"] == PASSWORD_RESET_REQUESTED_MESSAGE
    assert len(mailbox.sent) == 1
    to, _, body = mailbox.sent[0]
    assert to == EMAIL
    assert token_from(body)


def test_email_is_normalized_before_lookup(client, registered_user, mailbox):
    api, _ = client
    assert forgot(api, "  Alumna@Example.COM ").status_code == 200
    assert mailbox.sent[0][0] == EMAIL


def test_unknown_or_inactive_email_gets_same_message_without_email(client, registered_user, mailbox):
    api, SessionLocal = client
    unknown = forgot(api, "nadie@example.com")
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == EMAIL)).is_active = False
        db.commit()
    inactive = forgot(api)
    for response in (unknown, inactive):
        assert response.status_code == 200
        assert response.json()["message"] == PASSWORD_RESET_REQUESTED_MESSAGE
    assert mailbox.sent == []


def test_only_token_hash_is_persisted(client, registered_user, mailbox):
    api, SessionLocal = client
    token = request_token(api, mailbox)
    with SessionLocal() as db:
        stored = db.scalars(select(PasswordResetToken)).all()
    assert len(stored) == 1
    assert stored[0].token_hash != token
    assert len(stored[0].token_hash) == 64


def test_reset_changes_password_and_old_one_stops_working(client, registered_user, mailbox):
    api, _ = client
    token = request_token(api, mailbox)
    response = reset(api, token)
    assert response.status_code == 200
    assert response.json()["message"] == PASSWORD_RESET_SUCCESS_MESSAGE
    assert login(api, OLD_PASSWORD).status_code == 401
    assert login(api, NEW_PASSWORD).status_code == 200


def test_used_token_is_rejected(client, registered_user, mailbox):
    api, _ = client
    token = request_token(api, mailbox)
    assert reset(api, token).status_code == 200
    reused = reset(api, token, "OtraClave2026")
    assert reused.status_code == 400
    assert reused.json()["detail"] == INVALID_RESET_TOKEN_MESSAGE


def test_expired_token_is_rejected(client, registered_user, mailbox):
    api, SessionLocal = client
    token = request_token(api, mailbox)
    with SessionLocal() as db:
        stored = db.scalar(select(PasswordResetToken))
        stored.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
    response = reset(api, token)
    assert response.status_code == 400
    assert response.json()["detail"] == INVALID_RESET_TOKEN_MESSAGE
    assert login(api, OLD_PASSWORD).status_code == 200


def test_unknown_token_is_rejected(client, registered_user, mailbox):
    api, _ = client
    response = reset(api, "token-inexistente")
    assert response.status_code == 400
    assert response.json()["detail"] == INVALID_RESET_TOKEN_MESSAGE


def test_token_of_inactive_account_is_rejected(client, registered_user, mailbox):
    api, SessionLocal = client
    token = request_token(api, mailbox)
    with SessionLocal() as db:
        db.scalar(select(User).where(User.email == EMAIL)).is_active = False
        db.commit()
    assert reset(api, token).json()["detail"] == INVALID_RESET_TOKEN_MESSAGE


def test_only_latest_token_is_valid(client, registered_user, mailbox):
    api, _ = client
    first = request_token(api, mailbox)
    second = request_token(api, mailbox)
    rejected = reset(api, first)
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == INVALID_RESET_TOKEN_MESSAGE
    assert reset(api, second).status_code == 200


def test_weak_password_is_rejected_without_consuming_token(client, registered_user, mailbox):
    api, _ = client
    token = request_token(api, mailbox)
    weak = reset(api, token, "debil")
    assert weak.status_code == 400
    assert weak.json()["detail"] == PASSWORD_REQUIREMENTS_MESSAGE
    assert reset(api, token).status_code == 200


def test_reset_unlocks_account_and_resets_attempts(client, registered_user, mailbox):
    api, SessionLocal = client
    for _ in range(5):
        login(api, "WrongPass123")
    assert login(api, OLD_PASSWORD).status_code == 423
    token = request_token(api, mailbox)
    assert reset(api, token).status_code == 200
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        assert user.failed_login_attempts == 0
        assert user.locked_until is None
    assert login(api, NEW_PASSWORD).status_code == 200


def test_reset_revokes_all_active_sessions(client, registered_user, mailbox):
    api, _ = client
    tokens = [login(api, OLD_PASSWORD).json()["access_token"] for _ in range(2)]
    for access_token in tokens:
        assert api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}).status_code == 200
    assert reset(api, request_token(api, mailbox)).status_code == 200
    for access_token in tokens:
        assert api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}).status_code == 401
