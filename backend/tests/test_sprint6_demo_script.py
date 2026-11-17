"""Script de demo del Sprint 6: deja cada escenario listo y es idempotente."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from backend.scripts.prepare_sprint6_demo import (
    JOAQUIN,
    LUCAS,
    LUCIA,
    MATEO,
    SOFIA,
    TOMAS,
    VALENTINA,
    prepare_sprint6_demo_data,
)
from backend.src.models.achievement import AchievementCongratulation, StudentAchievement
from backend.src.models.conversation import ConversationMessage
from backend.src.models.informal_payment import InformalPayment
from backend.src.models.notification import Notification
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.services.conversation_service import list_conversations
from backend.src.services.informal_payment_service import list_subscriptions
from backend.src.services.streak_service import get_student_streak
from backend.src.services.technical_query_service import (
    list_pending_notes,
    pending_queries_by_student,
)
from backend.tests.test_seed_demo import create_test_db


def user(db, email: str) -> User:
    return db.scalar(select(User).where(User.email == email))


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory):
    receipts = tmp_path_factory.mktemp("receipts")
    patch = pytest.MonkeyPatch()
    patch.setattr("backend.src.services.student_subscription_service.RECEIPTS_DIR", receipts)
    db = create_test_db()
    prepare_sprint6_demo_data(db)
    yield db, receipts
    db.close()
    patch.undo()


def test_subscriptions_show_the_three_states_and_a_pending_report(demo_db):
    db, receipts = demo_db
    today = datetime.now(UTC).date()

    items = {item.student_name: item for item in list_subscriptions(db, user(db, LUCAS), today)}

    by_email = {email: item for email, item in (
        (VALENTINA, next(i for n, i in items.items() if n.startswith("Valentina"))),
        (MATEO, next(i for n, i in items.items() if n.startswith("Mateo"))),
        (LUCIA, next(i for n, i in items.items() if n.startswith("Lucía"))),
    )}
    assert by_email[VALENTINA].status == "AL_DIA"
    assert by_email[MATEO].status == "POR_VENCER"
    assert by_email[MATEO].days_until_due == 3
    assert by_email[LUCIA].status == "VENCIDA"
    assert by_email[LUCIA].pending_payment_count == 1
    assert any(name.startswith("Sofía") for name in items)  # para dar de baja en vivo
    others = [i for n, i in items.items() if not n.startswith(("Mateo", "Lucía"))]
    assert all(item.status == "AL_DIA" for item in others)  # solo Mateo y Lucía muestran alertas
    statuses = set(db.scalars(select(InformalPayment.status)))
    assert {"CONFIRMADO", "PENDIENTE_CONFIRMACION"} <= statuses
    assert len(list(receipts.rglob("*.pdf"))) == 2


def test_chat_has_unread_message_pending_query_and_pinned_note(demo_db):
    db, _ = demo_db

    lucas_chat = next(c for c in list_conversations(db, user(db, LUCAS)) if c.counterpart_name.startswith("Valentina"))
    [group] = pending_queries_by_student(db, user(db, LUCAS))
    notes = list_pending_notes(db, user(db, VALENTINA))

    assert lucas_chat.unread_count >= 1
    assert [q.exercise.name for q in group.queries] == ["Peso Muerto"]
    assert [note.exercise_name for note in notes] == ["Sentadilla con Barra"]  # Día 1: se ve al iniciar la sesión


def test_streaks_and_achievements(demo_db):
    db, _ = demo_db

    valentina = get_student_streak(db, user(db, VALENTINA))
    joaquin = get_student_streak(db, user(db, JOAQUIN))

    assert valentina.current_weeks >= 5
    assert joaquin.current_weeks == 0
    assert joaquin.max_weeks == 3
    reset = db.scalar(select(Notification).where(
        Notification.recipient_id == user(db, JOAQUIN).id, Notification.type == "STREAK_RESET"
    ))
    assert reset is not None
    codes = set(db.scalars(select(StudentAchievement.code).where(
        StudentAchievement.student_id == user(db, VALENTINA).student_profile.id
    )))
    assert {"FIRST_SESSION", "TEN_SESSIONS", "STREAK_4_WEEKS"} <= codes
    assert db.scalar(select(func.count(AchievementCongratulation.id))) == 1
    tomas_id = user(db, TOMAS).student_profile.id
    assert db.scalar(select(func.count(WorkoutSession.id)).where(
        WorkoutSession.student_id == tomas_id, WorkoutSession.finished_at.is_not(None)
    )) == 9


def test_running_twice_does_not_duplicate(demo_db):
    db, _ = demo_db
    before = {
        "payments": db.scalar(select(func.count(InformalPayment.id))),
        "messages": db.scalar(select(func.count(ConversationMessage.id))),
        "sessions": db.scalar(select(func.count(WorkoutSession.id))),
        "achievements": db.scalar(select(func.count(StudentAchievement.id))),
        "congratulations": db.scalar(select(func.count(AchievementCongratulation.id))),
    }

    prepare_sprint6_demo_data(db)

    after = {
        "payments": db.scalar(select(func.count(InformalPayment.id))),
        "messages": db.scalar(select(func.count(ConversationMessage.id))),
        "sessions": db.scalar(select(func.count(WorkoutSession.id))),
        "achievements": db.scalar(select(func.count(StudentAchievement.id))),
        "congratulations": db.scalar(select(func.count(AchievementCongratulation.id))),
    }
    assert after == before
    assert user(db, SOFIA) is not None
