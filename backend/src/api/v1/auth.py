from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from backend.src.api.v1.deps import (
    DbDep,
    get_current_session,
    get_current_user,
    get_email_sender,
)
from backend.src.core.config import API_V1_PREFIX, PASSWORD_RESET_TOKEN_MINUTES
from backend.src.core.constants import (
    PASSWORD_RESET_EMAIL_BODY,
    PASSWORD_RESET_EMAIL_SUBJECT,
    PASSWORD_RESET_REQUESTED_MESSAGE,
    PASSWORD_RESET_SUCCESS_MESSAGE,
)
from backend.src.models.user import User, UserSession
from backend.src.schemas.auth import (
    AuthTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from backend.src.services.auth_service import (
    AuthError,
    login_user,
    register_user,
    request_password_reset,
    reset_password,
    revoke_session,
)
from backend.src.services.email_service import EmailSender

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
        headers = {"Retry-After": str(exc.retry_after_seconds)} if exc.retry_after_seconds is not None else None
        raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers=headers) from exc
    return AuthTokenResponse(access_token=token, expires_in=expires_in, user=public_user(user))


@router.post("/logout")
def logout(session_data: Annotated[tuple[User, UserSession], Depends(get_current_session)], db: DbDep) -> dict[str, str]:
    _, user_session = session_data
    revoke_session(db, user_session)
    return {"message": "Sesión cerrada correctamente."}


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: DbDep,
    background_tasks: BackgroundTasks,
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> MessageResponse:
    reset_request = request_password_reset(db, str(payload.email))
    if reset_request is not None:
        email, link = reset_request
        body = PASSWORD_RESET_EMAIL_BODY.format(link=link, minutes=PASSWORD_RESET_TOKEN_MINUTES)
        background_tasks.add_task(email_sender.send, email, PASSWORD_RESET_EMAIL_SUBJECT, body)
    return MessageResponse(message=PASSWORD_RESET_REQUESTED_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password_endpoint(payload: ResetPasswordRequest, db: DbDep) -> MessageResponse:
    try:
        reset_password(db, payload.token, payload.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return MessageResponse(message=PASSWORD_RESET_SUCCESS_MESSAGE)


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return public_user(user)
