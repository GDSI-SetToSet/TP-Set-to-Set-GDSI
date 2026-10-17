from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from backend.src.api.v1.deps import DbDep, get_current_session, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User, UserSession
from backend.src.schemas.auth import (
    AuthTokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from backend.src.services.auth_service import (
    AuthError,
    login_user,
    register_user,
    revoke_session,
)

router = APIRouter(prefix=f"{API_V1_PREFIX}/auth", tags=["authentication"])


def public_user(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbDep) -> UserResponse:
    try:
        user = register_user(db, str(payload.email), payload.password, payload.role)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return public_user(user)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: DbDep) -> AuthTokenResponse:
    try:
        user, token, expires_in = login_user(db, str(payload.email), payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return AuthTokenResponse(access_token=token, expires_in=expires_in, user=public_user(user))


@router.post("/logout")
def logout(session_data: Annotated[tuple[User, UserSession], Depends(get_current_session)], db: DbDep) -> dict[str, str]:
    _, user_session = session_data
    revoke_session(db, user_session)
    return {"message": "Sesión cerrada correctamente."}


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return public_user(user)
