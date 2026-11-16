"""Esquemas del canal de mensajes (US-21) y de las consultas técnicas (US-62)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MESSAGE_MAX_LENGTH = 2000
MESSAGE_BODY_MESSAGE = "Escribí un mensaje (hasta 2000 caracteres)."
QUERY_BODY_MESSAGE = "Escribí tu consulta (hasta 2000 caracteres)."
SET_NUMBER_MESSAGE = "La serie debe ser un número entre 1 y 50."
EXERCISE_REQUIRED_MESSAGE = "Indicá el ejercicio de la consulta."

MessageKind = Literal["TEXT", "TECHNICAL_QUERY"]
Role = Literal["TRAINER", "STUDENT"]


def _clean_body(value: object, message: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not 1 <= len(text) <= MESSAGE_MAX_LENGTH:
        raise ValueError(message)
    return text


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class MessageCreate(BaseModel):
    body: str | None = Field(default=None, validate_default=True)
    reply_to_message_id: str | None = None
    pin_as_technical_note: bool = False

    @field_validator("body", mode="before")
    @classmethod
    def validate_body(cls, value: object) -> str:
        return _clean_body(value, MESSAGE_BODY_MESSAGE)

    @field_validator("reply_to_message_id", mode="before")
    @classmethod
    def normalize_reply(cls, value: object) -> object:
        return _blank_to_none(value)


class TechnicalQueryCreate(BaseModel):
    exercise_id: str | None = Field(default=None, validate_default=True)
    body: str | None = Field(default=None, validate_default=True)
    session_id: str | None = None
    set_number: int | None = None

    @field_validator("exercise_id", mode="before")
    @classmethod
    def require_exercise(cls, value: object) -> str:
        value = _blank_to_none(value)
        if value is None or not isinstance(value, str):
            raise ValueError(EXERCISE_REQUIRED_MESSAGE)
        return value

    @field_validator("body", mode="before")
    @classmethod
    def validate_body(cls, value: object) -> str:
        return _clean_body(value, QUERY_BODY_MESSAGE)

    @field_validator("session_id", mode="before")
    @classmethod
    def normalize_session(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("set_number", mode="before")
    @classmethod
    def validate_set_number(cls, value: object) -> object:
        value = _blank_to_none(value)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 50:
            raise ValueError(SET_NUMBER_MESSAGE)
        return value


class NoteAcknowledge(BaseModel):
    session_id: str | None = None


class ExerciseRef(BaseModel):
    id: str | None
    name: str


class NoteRef(BaseModel):
    id: str
    acknowledged_at: datetime | None


class LastMessage(BaseModel):
    body: str
    created_at: datetime
    is_mine: bool
    kind: MessageKind


class ConversationSummary(BaseModel):
    relationship_id: str
    status: str
    can_send: bool
    counterpart_name: str
    counterpart_role: Role
    trainer_id: str
    student_id: str
    plan_title: str | None
    unread_count: int
    last_message: LastMessage | None


class MessageView(BaseModel):
    id: str
    kind: MessageKind
    body: str
    sender_role: Role
    sender_name: str
    is_mine: bool
    created_at: datetime
    read_at: datetime | None
    exercise: ExerciseRef | None
    session_id: str | None
    set_number: int | None
    reply_to_message_id: str | None
    is_answered: bool
    technical_note: NoteRef | None


class ConversationDetail(BaseModel):
    conversation: ConversationSummary
    messages: list[MessageView]


class PendingQueriesGroup(BaseModel):
    student_id: str
    student_name: str
    relationship_id: str
    queries: list[MessageView]


class ExerciseQueryThread(BaseModel):
    query: MessageView
    replies: list[MessageView]


class TechnicalNoteView(BaseModel):
    id: str
    relationship_id: str
    exercise_id: str | None
    exercise_name: str
    body: str
    trainer_name: str
    created_at: datetime
    acknowledged_at: datetime | None
