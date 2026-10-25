import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from backend.src.core.config import JWT_ALGORITHM, JWT_SECRET, SESSION_DAYS
from backend.src.core.constants import (
    PASSWORD_LOWERCASE_PATTERN,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PASSWORD_NUMBER_PATTERN,
    PASSWORD_REQUIREMENTS_MESSAGE,
    PASSWORD_UPPERCASE_PATTERN,
)

password_hasher = PasswordHasher()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def password_policy_error(password: str) -> str | None:
    meets_all_requirements = (
        PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH
        and re.search(PASSWORD_UPPERCASE_PATTERN, password) is not None
        and re.search(PASSWORD_LOWERCASE_PATTERN, password) is not None
        and re.search(PASSWORD_NUMBER_PATTERN, password) is not None
    )
    return None if meets_all_requirements else PASSWORD_REQUIREMENTS_MESSAGE


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_reset_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_reset_token(token)


def create_access_token(user_id: str, role: str, jti: str, expires_at: datetime) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "jti": jti,
        "iat": datetime.now(UTC),
        "exp": expires_at.replace(tzinfo=UTC) if expires_at.tzinfo is None else expires_at,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def create_session_credentials(user_id: str, role: str, now: datetime) -> tuple[str, str, datetime]:
    jti = str(uuid4())
    expires_at = now + timedelta(days=SESSION_DAYS)
    token = create_access_token(user_id, role, jti, expires_at)
    return token, jti, expires_at
