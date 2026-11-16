"""Consultas técnicas sobre ejercicios y notas técnicas fijadas (US-62).

La consulta es un mensaje TECHNICAL_QUERY dentro de la conversación del vínculo (US-21,
Decisión Alternativa B). Está pendiente hasta que el entrenador la responde.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.models.conversation import ConversationMessage, TechnicalNote
from backend.src.models.exercise import Exercise
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.schemas.conversation import (
    ExerciseQueryThread,
    MessageView,
    PendingQueriesGroup,
    TechnicalNoteView,
    TechnicalQueryCreate,
)
from backend.src.services.conversation_service import (
    ACTIVE,
    ConversationError,
    message_views,
    parties,
    preview,
    require_active,
    resolve,
    utc_now,
)
from backend.src.services.notification_service import create_notification

TECHNICAL_QUERY = "TECHNICAL_QUERY"
ONLY_STUDENT_ASKS = "Solo el alumno puede crear consultas técnicas."
ONLY_TRAINERS = "Esta acción está disponible solo para entrenadores."
ONLY_STUDENTS = "Esta acción está disponible solo para alumnos."
EXERCISE_NOT_FOUND = "El ejercicio no existe."
SESSION_INVALID = "La sesión no pertenece a este entrenamiento."
NOTE_NOT_FOUND = "No se encontró la nota técnica."


def create_query(db: Session, user: User, relationship_id: str, data: TechnicalQueryCreate) -> MessageView:
    """Escenario 1: el alumno consulta sobre un ejercicio; el entrenador recibe una notificación (escenario 2)."""
    relationship, role = resolve(db, user, relationship_id)
    if role != STUDENT_ROLE:
        raise ConversationError(403, ONLY_STUDENT_ASKS)
    require_active(relationship)
    exercise = db.get(Exercise, data.exercise_id)
    # Solo ejercicios vigentes de la biblioteca del entrenador del vínculo (los de la rutina del alumno).
    if exercise is None or exercise.deleted_at is not None or exercise.trainer_id != relationship.trainer_id:
        raise ConversationError(422, EXERCISE_NOT_FOUND, [{"field": "exercise_id", "message": EXERCISE_NOT_FOUND}])
    if data.session_id is not None:
        session = db.get(WorkoutSession, data.session_id)
        if session is None or session.relationship_id != relationship.id or session.student_id != relationship.student_id:
            raise ConversationError(422, SESSION_INVALID, [{"field": "session_id", "message": SESSION_INVALID}])

    message = ConversationMessage(
        relationship_id=relationship.id,
        sender_user_id=user.id,
        sender_role=STUDENT_ROLE,
        kind=TECHNICAL_QUERY,
        body=data.body,
        exercise_id=exercise.id,
        exercise_name=exercise.name,
        session_id=data.session_id,
        set_number=data.set_number,
        created_at=utc_now(),
    )
    db.add(message)
    db.flush()
    names = parties(db, relationship)
    create_notification(
        db,
        recipient_id=names.trainer_user_id,
        type=TECHNICAL_QUERY,
        title=preview(f"Consulta técnica de {names.student_name}", 150),
        message=preview(f"{exercise.name}: {data.body}"),
        related_entity_type="ConversationMessage",
        related_entity_id=message.id,
        related_student_id=relationship.student_id,
        related_session_id=data.session_id,
    )
    db.commit()
    db.refresh(message)
    return message_views(db, relationship, [message], user.id)[0]


def pending_queries_by_student(db: Session, user: User) -> list[PendingQueriesGroup]:
    """Escenario 2: consultas sin respuesta de los vínculos activos, agrupadas por alumno (más antiguas primero)."""
    if user.role != TRAINER_ROLE:
        raise ConversationError(403, ONLY_TRAINERS)
    if user.trainer_profile is None:
        return []
    reply = aliased(ConversationMessage)
    pending = list(
        db.scalars(
            select(ConversationMessage)
            .join(TrainingRelationship, ConversationMessage.relationship_id == TrainingRelationship.id)
            .where(
                TrainingRelationship.trainer_id == user.trainer_profile.id,
                TrainingRelationship.status == ACTIVE,
                ConversationMessage.kind == TECHNICAL_QUERY,
                ~select(reply.id).where(reply.reply_to_message_id == ConversationMessage.id).exists(),
            )
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )
    by_relationship: dict[str, list[ConversationMessage]] = {}
    for message in pending:
        by_relationship.setdefault(message.relationship_id, []).append(message)
    groups = []
    for relationship_id, messages in by_relationship.items():
        relationship = db.get(TrainingRelationship, relationship_id)
        groups.append(
            PendingQueriesGroup(
                student_id=relationship.student_id,
                student_name=parties(db, relationship).student_name,
                relationship_id=relationship.id,
                queries=message_views(db, relationship, messages, user.id),
            )
        )
    return groups


def exercise_threads(
    db: Session, user: User, relationship_id: str, exercise_id: str
) -> list[ExerciseQueryThread]:
    """Escenario 4: consultas del ejercicio con sus respuestas, para cualquiera de las dos partes."""
    relationship, _ = resolve(db, user, relationship_id)
    queries = list(
        db.scalars(
            select(ConversationMessage)
            .where(
                ConversationMessage.relationship_id == relationship.id,
                ConversationMessage.kind == TECHNICAL_QUERY,
                ConversationMessage.exercise_id == exercise_id,
            )
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )
    if not queries:
        return []
    replies = list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.reply_to_message_id.in_([q.id for q in queries]))
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )
    views = {view.id: view for view in message_views(db, relationship, queries + replies, user.id)}
    return [
        ExerciseQueryThread(
            query=views[query.id],
            replies=[views[r.id] for r in replies if r.reply_to_message_id == query.id],
        )
        for query in queries
    ]


def _note_view(db: Session, note: TechnicalNote) -> TechnicalNoteView:
    relationship = db.get(TrainingRelationship, note.relationship_id)
    message = db.get(ConversationMessage, note.message_id)
    return TechnicalNoteView(
        id=note.id,
        relationship_id=note.relationship_id,
        exercise_id=note.exercise_id,
        exercise_name=note.exercise_name,
        body=message.body,
        trainer_name=parties(db, relationship).trainer_name,
        created_at=note.created_at,
        acknowledged_at=note.acknowledged_at,
    )


def list_pending_notes(db: Session, user: User) -> list[TechnicalNoteView]:
    """Escenario 3: notas fijadas que el alumno todavía no confirmó, de sus vínculos activos."""
    if user.role != STUDENT_ROLE:
        raise ConversationError(403, ONLY_STUDENTS)
    if user.student_profile is None:
        return []
    notes = db.scalars(
        select(TechnicalNote)
        .join(TrainingRelationship, TechnicalNote.relationship_id == TrainingRelationship.id)
        .where(
            TrainingRelationship.student_id == user.student_profile.id,
            TrainingRelationship.status == ACTIVE,
            TechnicalNote.acknowledged_at.is_(None),
        )
        .order_by(TechnicalNote.created_at)
    )
    return [_note_view(db, note) for note in notes]


def acknowledge_note(db: Session, user: User, note_id: str, session_id: str | None) -> TechnicalNoteView:
    """El alumno confirma la nota ("Entendido"); idempotente."""
    if user.role != STUDENT_ROLE:
        raise ConversationError(403, ONLY_STUDENTS)
    note = db.get(TechnicalNote, note_id)
    relationship = db.get(TrainingRelationship, note.relationship_id) if note else None
    if (
        note is None
        or relationship is None
        or user.student_profile is None
        or relationship.student_id != user.student_profile.id
    ):
        raise ConversationError(404, NOTE_NOT_FOUND)
    if note.acknowledged_at is None:
        note.acknowledged_at = utc_now()
        note.acknowledged_session_id = session_id
        db.commit()
        db.refresh(note)
    return _note_view(db, note)
