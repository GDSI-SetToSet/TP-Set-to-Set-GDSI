from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.src.core.constants import STUDENT_ROLE, TRAINER_ROLE
from backend.src.models.notification import Notification
from backend.src.models.user import User
from backend.src.schemas.discovery import NotificationItem, NotificationListResponse


class NotificationError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_role(user: User, expected_role: str = STUDENT_ROLE) -> None:
    if user.role != expected_role:
        role_label = "entrenadores" if expected_role == TRAINER_ROLE else "alumnos"
        raise NotificationError(
            status.HTTP_403_FORBIDDEN,
            f"Esta acción está disponible solo para {role_label}.",
        )


def create_notification(
    db: Session,
    recipient_id: str,
    type: str,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    commit: bool = False,
) -> Notification:
    notification = Notification(
        recipient_id=recipient_id,
        type=type,
        title=title,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        is_read=False,
        created_at=utc_now(),
    )
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    else:
        db.flush()
    return notification


def list_user_notifications(
    db: Session,
    user: User,
    is_read: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    expected_role: str = STUDENT_ROLE,
) -> NotificationListResponse:
    _require_role(user, expected_role)
    query = select(Notification).where(Notification.recipient_id == user.id)
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)

    total_query = select(func.count(Notification.id)).where(Notification.recipient_id == user.id)
    if is_read is not None:
        total_query = total_query.where(Notification.is_read == is_read)
    total = db.scalar(total_query) or 0

    unread_query = select(func.count(Notification.id)).where(
        Notification.recipient_id == user.id,
        Notification.is_read.is_(False),
    )
    unread_count = db.scalar(unread_query) or 0

    items_query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    rows = db.scalars(items_query).all()

    return NotificationListResponse(
        items=[NotificationItem.model_validate(row) for row in rows],
        total=total,
        unread_count=unread_count,
    )


def mark_notification_as_read(
    db: Session,
    user: User,
    notification_id: str,
    expected_role: str = STUDENT_ROLE,
) -> NotificationItem:
    _require_role(user, expected_role)
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise NotificationError(status.HTTP_404_NOT_FOUND, "Notificación no encontrada.")
    if notification.recipient_id != user.id:
        raise NotificationError(
            status.HTTP_403_FORBIDDEN,
            "No tenés permiso para marcar esta notificación.",
        )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = utc_now()
        db.commit()
        db.refresh(notification)
    return NotificationItem.model_validate(notification)
