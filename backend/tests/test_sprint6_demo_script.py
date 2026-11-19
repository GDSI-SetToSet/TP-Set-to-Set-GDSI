"""Script de demo del Sprint 6: deja cada escenario listo y es idempotente."""

from datetime import UTC, date, datetime, timedelta

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
    due_soon_start_date,
    prepare_sprint6_demo_data,
)
from backend.src.models.achievement import AchievementCongratulation, StudentAchievement
from backend.src.models.conversation import ConversationMessage, TechnicalNote
from backend.src.models.informal_payment import InformalPayment
from backend.src.models.notification import Notification
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.services.conversation_service import list_conversations
from backend.src.services.informal_payment_service import list_subscriptions
from backend.src.services.streak_service import get_student_streak
from backend.src.services.subscription_service import (
    DUE_SOON_DAYS,
    compute_due_date,
    subscription_status,
)
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
    expected_mateo_days = (compute_due_date(due_soon_start_date(today), 0) - today).days
    assert by_email[MATEO].days_until_due == expected_mateo_days
    assert 1 <= by_email[MATEO].days_until_due <= DUE_SOON_DAYS
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
    db, receipts = demo_db

    def counts():
        return {
            "payments": db.scalar(select(func.count(InformalPayment.id))),
            "messages": db.scalar(select(func.count(ConversationMessage.id))),
            "notes": db.scalar(select(func.count(TechnicalNote.id))),
            "notifications": db.scalar(select(func.count(Notification.id))),
            "sessions": db.scalar(select(func.count(WorkoutSession.id))),
            "achievements": db.scalar(select(func.count(StudentAchievement.id))),
            "congratulations": db.scalar(select(func.count(AchievementCongratulation.id))),
            "receipt_files": len(list(receipts.rglob("*.pdf"))),
        }

    before = counts()
    today = datetime.now(UTC).date()
    subs_before = [
        (s.student_name, s.status, s.due_date, s.days_until_due, s.pending_payment_count)
        for s in list_subscriptions(db, user(db, LUCAS), today)
    ]

    prepare_sprint6_demo_data(db)
    prepare_sprint6_demo_data(db)

    assert counts() == before
    subs_after = [
        (s.student_name, s.status, s.due_date, s.days_until_due, s.pending_payment_count)
        for s in list_subscriptions(db, user(db, LUCAS), today)
    ]
    assert subs_after == subs_before
    assert user(db, SOFIA) is not None


@pytest.mark.parametrize(
    ("today", "expected_days"),
    [
        # Fin de febrero no bisiesto y bisiesto
        (date(2025, 2, 28), 3),
        (date(2026, 2, 28), 3),
        (date(2024, 2, 28), 3),
        (date(2024, 2, 29), 3),
        (date(2028, 2, 29), 3),
        # Transición febrero → marzo (días 26–31 de marzo donde add_months recorta al 28/29)
        (date(2024, 3, 26), 3),
        (date(2024, 3, 27), 2),
        (date(2024, 3, 28), 4),
        (date(2024, 3, 29), 3),
        (date(2024, 3, 30), 3),
        (date(2024, 3, 31), 3),
        (date(2025, 3, 26), 2),
        (date(2025, 3, 27), 1),
        (date(2025, 3, 28), 4),
        (date(2025, 3, 29), 3),
        (date(2025, 3, 30), 3),
        (date(2025, 3, 31), 3),
        (date(2026, 3, 27), 1),
        (date(2026, 3, 28), 4),
        (date(2026, 3, 29), 3),
        (date(2026, 3, 30), 3),
        (date(2026, 3, 31), 3),
        # Meses de 30 y 31 días y cruce de año
        (date(2026, 4, 28), 3),
        (date(2026, 4, 29), 3),
        (date(2026, 4, 30), 3),
        (date(2026, 5, 28), 2),
        (date(2026, 5, 31), 3),
        (date(2026, 10, 28), 2),
        (date(2026, 12, 28), 2),
        (date(2026, 12, 31), 3),
        (date(2027, 1, 1), 3),
    ],
)
def test_due_soon_start_date_february_march_and_month_end_boundaries(today: date, expected_days: int):
    start = due_soon_start_date(today)
    due = compute_due_date(start, 0)
    status, days = subscription_status(due, today)

    assert start <= today
    assert status == "POR_VENCER"
    assert 1 <= days <= DUE_SOON_DAYS
    assert days == expected_days


def test_due_soon_start_date_consistent_across_full_leap_cycle():
    day = date(2024, 1, 1)
    while day <= date(2028, 12, 31):
        start = due_soon_start_date(day)
        due = compute_due_date(start, 0)
        status, days = subscription_status(due, day)
        assert start <= day
        assert status == "POR_VENCER"
        assert 1 <= days <= DUE_SOON_DAYS
        exact_target_exists = any(
            (day - timedelta(days=offset)) <= day
            and compute_due_date(day - timedelta(days=offset), 0) == day + timedelta(days=3)
            for offset in range(24, 33)
        )
        if exact_target_exists:
            assert days == 3
        day += timedelta(days=1)


@pytest.mark.parametrize(
    "target_today",
    [
        date(2026, 2, 28),
        date(2028, 2, 29),
        date(2026, 3, 27),
        date(2026, 3, 28),
        date(2026, 3, 30),
        date(2026, 3, 31),
        date(2026, 5, 28),
        date(2026, 12, 31),
    ],
)
def test_demo_data_consistent_on_month_boundary_dates(tmp_path, monkeypatch, target_today: date):
    receipts = tmp_path / "receipts"
    monkeypatch.setattr("backend.src.services.student_subscription_service.RECEIPTS_DIR", receipts)
    db = create_test_db()
    try:
        summary = prepare_sprint6_demo_data(db, today=target_today)
        items = {item.student_name: item for item in list_subscriptions(db, user(db, LUCAS), target_today)}

        valentina = next(i for n, i in items.items() if n.startswith("Valentina"))
        mateo = next(i for n, i in items.items() if n.startswith("Mateo"))
        lucia = next(i for n, i in items.items() if n.startswith("Lucía"))
        sofia = next(i for n, i in items.items() if n.startswith("Sofía"))
        joaquin = next(i for n, i in items.items() if n.startswith("Joaquín"))

        assert valentina.status == "AL_DIA"
        assert mateo.status == "POR_VENCER"
        assert 1 <= mateo.days_until_due <= DUE_SOON_DAYS
        assert f"en {mateo.days_until_due} " in summary["Mateo"]
        assert lucia.status == "VENCIDA"
        assert lucia.pending_payment_count == 1
        assert sofia.status == "AL_DIA"
        assert joaquin.status == "AL_DIA"
    finally:
        db.close()
