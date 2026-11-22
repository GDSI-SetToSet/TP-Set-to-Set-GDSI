"""Rutas del canal de mensajes (US-21) y de las consultas técnicas (US-62)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.src.api.v1.deps import DbDep, get_current_user
from backend.src.core.config import API_V1_PREFIX
from backend.src.models.user import User
from backend.src.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    ExerciseQueryThread,
    MessageCreate,
    MessageView,
    NoteAcknowledge,
    PendingQueriesGroup,
    TechnicalNoteView,
    TechnicalQueryCreate,
)
from backend.src.services.conversation_service import (
    ConversationError,
    get_conversation,
    list_conversations,
    mark_read,
    send_message,
)
from backend.src.services.technical_query_service import (
    acknowledge_note,
    create_query,
    exercise_threads,
    list_pending_notes,
    pending_queries_by_student,
)

router = APIRouter(prefix=API_V1_PREFIX, tags=["conversations"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def handle_error(error: ConversationError) -> None:
    detail: str | dict[str, object] = error.detail
    if error.errors is not None:
        detail = {"detail": error.detail, "errors": error.errors}
    raise HTTPException(status_code=error.status_code, detail=detail) from error


@router.get("/conversations", response_model=list[ConversationSummary])
def own_conversations(user: CurrentUser, db: DbDep) -> list[ConversationSummary]:
    """US-21: conversaciones del usuario (una por vínculo)."""
    return list_conversations(db, user)


@router.get("/conversations/{relationship_id}/messages", response_model=ConversationDetail)
def conversation_messages(relationship_id: str, user: CurrentUser, db: DbDep) -> ConversationDetail:
    """US-21 escenario 3: historial completo."""
    try:
        return get_conversation(db, user, relationship_id)
    except ConversationError as error:
        handle_error(error)


@router.post(
    "/conversations/{relationship_id}/messages",
    response_model=MessageView,
    status_code=status.HTTP_201_CREATED,
)
def conversation_send(relationship_id: str, payload: MessageCreate, user: CurrentUser, db: DbDep) -> MessageView:
    """US-21: enviar mensaje; US-62: responder una consulta y fijarla como nota técnica."""
    try:
        return send_message(db, user, relationship_id, payload)
    except ConversationError as error:
        handle_error(error)


@router.post("/conversations/{relationship_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def conversation_read(relationship_id: str, user: CurrentUser, db: DbDep) -> Response:
    """US-21 escenario 2: al abrir la conversación se marcan los mensajes y su notificación como leídos."""
    try:
        mark_read(db, user, relationship_id)
    except ConversationError as error:
        handle_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{relationship_id}/technical-queries",
    response_model=MessageView,
    status_code=status.HTTP_201_CREATED,
)
def conversation_technical_query(
    relationship_id: str, payload: TechnicalQueryCreate, user: CurrentUser, db: DbDep
) -> MessageView:
    """US-62 escenario 1: consulta técnica del alumno sobre un ejercicio."""
    try:
        return create_query(db, user, relationship_id, payload)
    except ConversationError as error:
        handle_error(error)


@router.get(
    "/conversations/{relationship_id}/exercises/{exercise_id}/technical-queries",
    response_model=list[ExerciseQueryThread],
)
def conversation_exercise_queries(
    relationship_id: str, exercise_id: str, user: CurrentUser, db: DbDep
) -> list[ExerciseQueryThread]:
    """US-62 escenario 4: historial de consultas y respuestas del ejercicio."""
    try:
        return exercise_threads(db, user, relationship_id, exercise_id)
    except ConversationError as error:
        handle_error(error)


@router.get("/trainers/me/technical-queries", response_model=list[PendingQueriesGroup])
def trainer_pending_queries(user: CurrentUser, db: DbDep) -> list[PendingQueriesGroup]:
    """US-62 escenario 2: bandeja de consultas pendientes agrupadas por alumno."""
    try:
        return pending_queries_by_student(db, user)
    except ConversationError as error:
        handle_error(error)


@router.get("/students/me/technical-notes", response_model=list[TechnicalNoteView])
def student_pending_notes(user: CurrentUser, db: DbDep) -> list[TechnicalNoteView]:
    """US-62 escenario 3: notas técnicas fijadas pendientes de confirmar."""
    try:
        return list_pending_notes(db, user)
    except ConversationError as error:
        handle_error(error)


@router.post("/students/me/technical-notes/{note_id}/acknowledge", response_model=TechnicalNoteView)
def student_acknowledge_note(
    note_id: str, user: CurrentUser, db: DbDep, payload: NoteAcknowledge | None = None
) -> TechnicalNoteView:
    """US-62 escenario 3: el alumno confirma la nota al iniciar el ejercicio."""
    try:
        return acknowledge_note(db, user, note_id, payload.session_id if payload else None)
    except ConversationError as error:
        handle_error(error)
