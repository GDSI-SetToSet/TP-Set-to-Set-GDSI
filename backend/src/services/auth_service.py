from datetime import UTC, datetime, timedelta
from math import ceil

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.src.core.config import LOCKOUT_MINUTES, MAX_FAILED_LOGINS, SESSION_DAYS
from backend.src.core.constants import (
    INVALID_CREDENTIALS_MESSAGE,
    LOCKED_ACCOUNT_MESSAGE,
    PASSWORD_MAX_LENGTH,
    SECONDS_PER_DAY,
    SECONDS_PER_MINUTE,
    STUDENT_ROLE,
    TRAINER_ROLE,
    VALID_USER_ROLES,
)
from backend.src.core.security import (
    create_session_credentials,
    hash_password,
    normalize_email,
    password_policy_error,
    verify_password,
)
from backend.src.models.user import User, UserSession


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str, retry_after_seconds: int | None = None):
        self.status_code = status_code
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def register_user(db: Session, email: str, password: str, role: str) -> User:
    email = normalize_email(email)
    error = password_policy_error(password)
    if error:
        raise AuthError(status.HTTP_400_BAD_REQUEST, error)
    if role not in VALID_USER_ROLES:
        raise AuthError(status.HTTP_400_BAD_REQUEST, f"El rol debe ser {TRAINER_ROLE} o {STUDENT_ROLE}.")
    if db.scalar(select(User).where(User.email == email)):
        raise AuthError(status.HTTP_409_CONFLICT, "El correo electrónico ya se encuentra registrado.")

    user = User(email=email, password_hash=hash_password(password), role=role, created_at=utc_now())
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AuthError(status.HTTP_409_CONFLICT, "El correo electrónico ya se encuentra registrado.") from exc
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str) -> tuple[User, str, int]:
    now = utc_now()
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS_MESSAGE)

    locked_until = user.locked_until
    if locked_until is not None and locked_until.tzinfo is not None:
        locked_until = locked_until.replace(tzinfo=None)
    if locked_until is not None and locked_until > now:
        remaining_seconds = max(1, ceil((locked_until - now).total_seconds()))
        remaining_minutes = ceil(remaining_seconds / SECONDS_PER_MINUTE)
        detail = LOCKED_ACCOUNT_MESSAGE.format(minutes=remaining_minutes)
        raise AuthError(status.HTTP_423_LOCKED, detail, retry_after_seconds=remaining_seconds)
    if locked_until is not None:
        user.locked_until = None
        user.failed_login_attempts = 0

    password_is_valid = len(password) <= PASSWORD_MAX_LENGTH and verify_password(password, user.password_hash)
    if not password_is_valid:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            db.commit()
            detail = LOCKED_ACCOUNT_MESSAGE.format(minutes=LOCKOUT_MINUTES)
            retry_after_seconds = LOCKOUT_MINUTES * SECONDS_PER_MINUTE
            raise AuthError(status.HTTP_423_LOCKED, detail, retry_after_seconds=retry_after_seconds)
        db.commit()
        raise AuthError(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS_MESSAGE)

    user.failed_login_attempts = 0
    user.locked_until = None
    token, jti, expires_at = create_session_credentials(user.id, user.role, now)
    db.add(UserSession(user_id=user.id, jti=jti, expires_at=expires_at))
    db.commit()
    db.refresh(user)
    return user, token, SESSION_DAYS * SECONDS_PER_DAY


def revoke_session(db: Session, user_session: UserSession) -> None:
    user_session.revoked_at = utc_now()
    db.commit()
