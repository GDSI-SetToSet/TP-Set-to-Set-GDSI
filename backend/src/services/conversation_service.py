"""Canal de mensajes entrenador–alumno (US-21).

La conversación es el vínculo de entrenamiento. Solo sus dos partes la leen (un tercero recibe
404, sin revelar si existe) y solo se envía con el vínculo ACTIVE. Sin WebSockets: el cliente
vuelve a pedir el historial periódicamente.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.models.conversation import ConversationMessage, TechnicalNote
from backend.src.models.notification import Notification
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    ExerciseRef,
    LastMessage,
    MessageCreate,
    MessageView,
    NoteRef,
)
from backend.src.services.notification_service import create_notification

NEW_MESSAGE = "NEW_MESSAGE"
ACTIVE = "ACTIVE"
NOT_FOUND = "No se encontró la conversación."
NOT_ACTIVE = "El vínculo de entrenamiento no está activo: no se pueden enviar mensajes."
ONLY_TRAINER_REPLIES = "Solo el entrenador puede responder consultas técnicas."
REPLY_INVALID = "La respuesta debe referirse a una consulta técnica de esta conversación."
PIN_REQUIRES_REPLY = "Solo se puede fijar como nota técnica una respuesta a una consulta."
PREVIEW_LENGTH = 140


class ConversationError(Exception):
    def __init__(self, status_code: int, detail: str, errors: list[dict[str, str]] | None = None):
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def preview(text: str, length: int = PREVIEW_LENGTH) -> str:
    text = " ".join(text.split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


@dataclass(frozen=True)
class Parties:
    """Las dos partes de un vínculo con sus usuarios y nombres visibles."""

    trainer_user_id: str
    student_user_id: str
    trainer_name: str
    student_name: str

    def name_of(self, user_id: str) -> str:
        return self.trainer_name if user_id == self.trainer_user_id else self.student_name

    def other(self, user_id: str) -> str:
        return self.student_user_id if user_id == self.trainer_user_id else self.trainer_user_id


def trainer_display_name(profile: TrainerProfile, email: str) -> str:
    return (profile.full_name or "").strip() or email


def student_display_name(profile: StudentProfile, email: str) -> str:
    name = " ".join(part for part in (profile.first_name, profile.last_name) if part).strip()
    return name or email


def parties(db: Session, relationship: TrainingRelationship) -> Parties:
    trainer = db.get(TrainerProfile, relationship.trainer_id)
    student = db.get(StudentProfile, relationship.student_id)
    trainer_user = db.get(User, trainer.user_id)
    student_user = db.get(User, student.user_id)
    return Parties(
        trainer_user_id=trainer_user.id,
        student_user_id=student_user.id,
        trainer_name=trainer_display_name(trainer, trainer_user.email),
        student_name=student_display_name(student, student_user.email),
    )


def resolve(db: Session, user: User, relationship_id: str) -> tuple[TrainingRelationship, str]:
    """Vínculo y rol del usuario en él; 404 si el usuario no es una de las partes."""
    relationship = db.get(TrainingRelationship, relationship_id)
    if relationship is not None:
        trainer = user.trainer_profile if user.role == TRAINER_ROLE else None
        student = user.student_profile if user.role == STUDENT_ROLE else None
        if trainer is not None and relationship.trainer_id == trainer.id:
            return relationship, TRAINER_ROLE
        if student is not None and relationship.student_id == student.id:
            return relationship, STUDENT_ROLE
    raise ConversationError(404, NOT_FOUND)


def require_active(relationship: TrainingRelationship) -> None:
    if relationship.status != ACTIVE:
        raise ConversationError(409, NOT_ACTIVE)


def message_views(
    db: Session, relationship: TrainingRelationship, messages: list[ConversationMessage], viewer_id: str
) -> list[MessageView]:
    if not messages:
        return []
    names = parties(db, relationship)
    ids = [m.id for m in messages]
    answered = set(
        db.scalars(
            select(ConversationMessage.reply_to_message_id).where(ConversationMessage.reply_to_message_id.in_(ids))
        )
    )
    notes = {
        note.message_id: note
        for note in db.scalars(select(TechnicalNote).where(TechnicalNote.message_id.in_(ids)))
    }
    views = []
    for message in messages:
        note = notes.get(message.id)
        views.append(
            MessageView(
                id=message.id,
                kind=message.kind,
                body=message.body,
                sender_role=message.sender_role,
                sender_name=names.name_of(message.sender_user_id),
                is_mine=message.sender_user_id == viewer_id,
                created_at=message.created_at,
                read_at=message.read_at,
                exercise=ExerciseRef(id=message.exercise_id, name=message.exercise_name)
                if message.exercise_name
                else None,
                session_id=message.session_id,
                set_number=message.set_number,
                reply_to_message_id=message.reply_to_message_id,
                is_answered=message.id in answered,
                technical_note=NoteRef(id=note.id, acknowledged_at=note.acknowledged_at) if note else None,
            )
        )
    return views


def _summary(
    db: Session,
    relationship: TrainingRelationship,
    role: str,
    viewer_id: str,
    unread: int,
    last: ConversationMessage | None,
    names: Parties | None = None,
) -> ConversationSummary:
    resolved_names = names if names is not None else parties(db, relationship)
    is_trainer = role == TRAINER_ROLE
    return ConversationSummary(
        relationship_id=relationship.id,
        status=relationship.status,
        can_send=relationship.status == ACTIVE,
        counterpart_name=resolved_names.student_name if is_trainer else resolved_names.trainer_name,
        counterpart_role=STUDENT_ROLE if is_trainer else TRAINER_ROLE,
        trainer_id=relationship.trainer_id,
        student_id=relationship.student_id,
        plan_title=relationship.plan.title if relationship.plan else None,
        unread_count=unread,
        last_message=LastMessage(
            body=preview(last.body),
            created_at=last.created_at,
            is_mine=last.sender_user_id == viewer_id,
            kind=last.kind,
        )
        if last
        else None,
    )


def _unread_counts(db: Session, relationship_ids: list[str], viewer_id: str) -> dict[str, int]:
    if not relationship_ids:
        return {}
    rows = db.execute(
        select(ConversationMessage.relationship_id, func.count(ConversationMessage.id))
        .where(
            ConversationMessage.relationship_id.in_(relationship_ids),
            ConversationMessage.sender_user_id != viewer_id,
            ConversationMessage.read_at.is_(None),
        )
        .group_by(ConversationMessage.relationship_id)
    ).all()
    return {rel_id: int(count) for rel_id, count in rows}


def _last_messages(db: Session, relationship_ids: list[str]) -> dict[str, ConversationMessage]:
    """Obtiene el último mensaje de cada conversación en una sola consulta SQL."""
    if not relationship_ids:
        return {}
    ranked = (
        select(
            ConversationMessage.id.label("msg_id"),
            func.row_number()
            .over(
                partition_by=ConversationMessage.relationship_id,
                order_by=(ConversationMessage.created_at.desc(), ConversationMessage.id.desc()),
            )
            .label("rn"),
        )
        .where(ConversationMessage.relationship_id.in_(relationship_ids))
        .subquery()
    )
    rows = db.scalars(
        select(ConversationMessage).join(ranked, ConversationMessage.id == ranked.c.msg_id).where(ranked.c.rn == 1)
    )
    return {msg.relationship_id: msg for msg in rows}


def _batch_parties(db: Session, relationships: list[TrainingRelationship]) -> dict[str, Parties]:
    if not relationships:
        return {}
    trainer_ids = {r.trainer_id for r in relationships}
    student_ids = {r.student_id for r in relationships}
    trainers = {tp.id: tp for tp in db.scalars(select(TrainerProfile).where(TrainerProfile.id.in_(trainer_ids)))}
    students = {sp.id: sp for sp in db.scalars(select(StudentProfile).where(StudentProfile.id.in_(student_ids)))}
    user_ids = {tp.user_id for tp in trainers.values()} | {sp.user_id for sp in students.values()}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
    result: dict[str, Parties] = {}
    for rel in relationships:
        tp = trainers[rel.trainer_id]
        sp = students[rel.student_id]
        tu = users[tp.user_id]
        su = users[sp.user_id]
        result[rel.id] = Parties(
            trainer_user_id=tu.id,
            student_user_id=su.id,
            trainer_name=trainer_display_name(tp, tu.email),
            student_name=student_display_name(sp, su.email),
        )
    return result


def list_conversations(db: Session, user: User) -> list[ConversationSummary]:
    """Vínculos activos del usuario y los terminados que tengan mensajes."""
    if user.role == TRAINER_ROLE and user.trainer_profile is not None:
        owner_filter = TrainingRelationship.trainer_id == user.trainer_profile.id
        role = TRAINER_ROLE
    elif user.role == STUDENT_ROLE and user.student_profile is not None:
        owner_filter = TrainingRelationship.student_id == user.student_profile.id
        role = STUDENT_ROLE
    else:
        return []
    has_messages = select(ConversationMessage.id).where(
        ConversationMessage.relationship_id == TrainingRelationship.id
    ).exists()
    relationships = list(
        db.scalars(
            select(TrainingRelationship)
            .options(selectinload(TrainingRelationship.plan))
            .where(owner_filter, or_(TrainingRelationship.status == ACTIVE, has_messages))
        )
    )
    rel_ids = [r.id for r in relationships]
    unread = _unread_counts(db, rel_ids, user.id)
    last_messages = _last_messages(db, rel_ids)
    names_by_rel = _batch_parties(db, relationships)
    summaries = [
        _summary(
            db,
            r,
            role,
            user.id,
            unread.get(r.id, 0),
            last_messages.get(r.id),
            names=names_by_rel.get(r.id),
        )
        for r in relationships
    ]
    with_messages = sorted(
        (s for s in summaries if s.last_message), key=lambda s: s.last_message.created_at, reverse=True
    )
    without = sorted((s for s in summaries if not s.last_message), key=lambda s: s.counterpart_name.lower())
    return [*with_messages, *without]


def get_conversation(db: Session, user: User, relationship_id: str) -> ConversationDetail:
    """US-21 escenario 3: historial completo en orden cronológico (también con el vínculo terminado)."""
    relationship, role = resolve(db, user, relationship_id)
    # ponytail: devuelve todo el historial en cada actualización; paginar por created_at si crece.
    messages = list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.relationship_id == relationship.id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )
    unread = _unread_counts(db, [relationship.id], user.id).get(relationship.id, 0)
    last = messages[-1] if messages else None
    return ConversationDetail(
        conversation=_summary(db, relationship, role, user.id, unread, last),
        messages=message_views(db, relationship, messages, user.id),
    )


def notify_new_message(
    db: Session, relationship: TrainingRelationship, sender_id: str, body: str
) -> None:
    """Una sola notificación sin leer por conversación y destinatario: se actualiza en vez de duplicarse."""
    names = parties(db, relationship)
    recipient_id = names.other(sender_id)
    sender_name = names.name_of(sender_id)
    unread = db.scalar(
        select(func.count(ConversationMessage.id)).where(
            ConversationMessage.relationship_id == relationship.id,
            ConversationMessage.sender_user_id == sender_id,
            ConversationMessage.read_at.is_(None),
        )
    ) or 1
    title = f"Nuevo mensaje de {sender_name}" if unread == 1 else f"{unread} mensajes nuevos de {sender_name}"
    title = preview(title, 150)
    existing = db.scalar(
        select(Notification).where(
            Notification.recipient_id == recipient_id,
            Notification.type == NEW_MESSAGE,
            Notification.related_entity_id == relationship.id,
            Notification.is_read.is_(False),
        )
    )
    if existing is not None:
        existing.title = title
        existing.message = preview(body)
        existing.created_at = utc_now()
        return
    create_notification(
        db,
        recipient_id=recipient_id,
        type=NEW_MESSAGE,
        title=title,
        message=preview(body),
        related_entity_type="TrainingRelationship",
        related_entity_id=relationship.id,
        related_student_id=relationship.student_id,
    )


def send_message(db: Session, user: User, relationship_id: str, data: MessageCreate) -> MessageView:
    """US-21: mensaje de texto. El entrenador puede responder una consulta (US-62) y fijarla como nota."""
    relationship, role = resolve(db, user, relationship_id)
    require_active(relationship)

    query: ConversationMessage | None = None
    if data.reply_to_message_id is not None:
        if role != TRAINER_ROLE:
            raise ConversationError(403, ONLY_TRAINER_REPLIES)
        query = db.get(ConversationMessage, data.reply_to_message_id)
        if query is None or query.relationship_id != relationship.id or query.kind != "TECHNICAL_QUERY":
            raise ConversationError(422, REPLY_INVALID, [{"field": "reply_to_message_id", "message": REPLY_INVALID}])
    if data.pin_as_technical_note and query is None:
        raise ConversationError(
            422, PIN_REQUIRES_REPLY, [{"field": "pin_as_technical_note", "message": PIN_REQUIRES_REPLY}]
        )

    now = utc_now()
    message = ConversationMessage(
        relationship_id=relationship.id,
        sender_user_id=user.id,
        sender_role=role,
        kind="TEXT",
        body=data.body,
        reply_to_message_id=query.id if query else None,
        created_at=now,
    )
    db.add(message)
    db.flush()
    if data.pin_as_technical_note and query is not None:
        db.add(
            TechnicalNote(
                relationship_id=relationship.id,
                message_id=message.id,
                exercise_id=query.exercise_id,
                exercise_name=query.exercise_name,
                created_at=now,
            )
        )
    if query is not None:
        db.execute(
            update(Notification)
            .where(
                Notification.recipient_id == user.id,
                Notification.type == "TECHNICAL_QUERY",
                Notification.related_entity_id == query.id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=now)
        )
    notify_new_message(db, relationship, user.id, data.body)
    db.commit()
    db.refresh(message)
    return message_views(db, relationship, [message], user.id)[0]


def mark_read(db: Session, user: User, relationship_id: str) -> None:
    """Marca como leídos los mensajes recibidos y la notificación agrupada de la conversación."""
    relationship, _ = resolve(db, user, relationship_id)
    now = utc_now()
    db.execute(
        update(ConversationMessage)
        .where(
            ConversationMessage.relationship_id == relationship.id,
            ConversationMessage.sender_user_id != user.id,
            ConversationMessage.read_at.is_(None),
        )
        .values(read_at=now)
    )
    db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user.id,
            Notification.type == NEW_MESSAGE,
            Notification.related_entity_id == relationship.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    db.commit()
