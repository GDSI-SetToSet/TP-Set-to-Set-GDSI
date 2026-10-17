from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE

Role = Literal[TRAINER_ROLE, STUDENT_ROLE]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: Role


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse
