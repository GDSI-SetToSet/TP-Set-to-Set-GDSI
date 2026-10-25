from typing import Annotated

import jwt
from backend.src.core.database import get_db
from backend.src.core.security import decode_access_token
from backend.src.models.user import User, UserSession
from backend.src.services.email_service import EmailSender, build_email_sender
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)
DbDep = Annotated[Session, Depends(get_db)]


def get_email_sender() -> EmailSender:
    return build_email_sender()


def get_current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbDep,
) -> tuple[User, UserSession]:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if not user_id or not jti:
            raise unauthorized
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise unauthorized from None

    session = db.scalar(select(UserSession).where(UserSession.jti == jti, UserSession.user_id == user_id))
    if session is None or session.revoked_at is not None:
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user, session


def get_current_user(session_data: Annotated[tuple[User, UserSession], Depends(get_current_session)]) -> User:
    return session_data[0]
