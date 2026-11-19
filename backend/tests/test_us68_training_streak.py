"""US-68: racha de semanas cumplidas (objetivo = días de la rutina vigente)."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from backend.src.models.notification import Notification
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession
from backend.src.services.streak_service import compute_streak, monday
from backend.tests.test_us60_rpe_api import (
    register_and_login,
    setup_routine_and_assignment,
)

STREAK = "/api/v1/students/me/streak"
MON = date(2026, 11, 16)  # lunes de la semana en curso en las pruebas puras


def weeks_ago(n: int) -> date:
    return MON - timedelta(weeks=n)


# Cálculo puro ----------------------------------------------------------------------------


def test_consecutive_met_weeks_build_the_streak():
    done = {weeks_ago(3): 3, weeks_ago(2): 3, weeks_ago(1): 4}
    result = compute_streak(3, weeks_ago(3), done, MON)
    assert (result.current_weeks, result.max_weeks, result.broken_week) == (3, 3, None)


def test_a_missed_week_resets_and_keeps_the_maximum():
    done = {weeks_ago(4): 3, weeks_ago(3): 3, weeks_ago(2): 3, weeks_ago(1): 2}
    result = compute_streak(3, weeks_ago(4), done, MON)
    assert (result.current_weeks, result.max_weeks) == (0, 3)
    assert result.broken_week == weeks_ago(1)


def test_streak_restarts_after_a_reset():
    done = {weeks_ago(4): 3, weeks_ago(3): 0, weeks_ago(2): 3, weeks_ago(1): 3}
    result = compute_streak(3, weeks_ago(4), done, MON)
    assert (result.current_weeks, result.max_weeks, result.broken_week) == (2, 2, None)


def test_current_week_never_adds_nor_breaks():
    met_early = compute_streak(2, weeks_ago(1), {weeks_ago(1): 2, MON: 5}, MON)
    nothing_yet = compute_streak(2, weeks_ago(1), {weeks_ago(1): 2}, MON)
    assert (met_early.current_weeks, met_early.this_week_sessions) == (1, 5)
    assert (nothing_yet.current_weeks, nothing_yet.this_week_sessions) == (1, 0)


def test_weeks_before_the_assignment_do_not_count():
    done = {weeks_ago(5): 0, weeks_ago(1): 1}
    assert compute_streak(1, weeks_ago(1), done, MON).current_weeks == 1
    assert compute_streak(1, MON, {MON: 3}, MON).current_weeks == 0  # asignada esta semana


def test_broken_only_when_a_streak_existed_and_no_target_means_no_streak():
    assert compute_streak(3, weeks_ago(3), {}, MON).broken_week is None  # nunca cumplió
    assert compute_streak(0, weeks_ago(3), {weeks_ago(1): 4}, MON).current_weeks == 0


# Integración -----------------------------------------------------------------------------


def _relationship_with_history(api, sessions, trainer, email: str, weeks_done: dict[int, int]) -> str:
    """Rutina de 1 día asignada hace 4 semanas; `weeks_done` = {semanas atrás: sesiones finalizadas}."""
    _, relationship_id, routine_id = setup_routine_and_assignment(api, sessions, trainer, email)
    now = datetime.now(UTC).replace(tzinfo=None)
    this_monday = monday(now.date())
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        relationship.routine_assigned_at = datetime.combine(this_monday - timedelta(weeks=4), datetime.min.time())
        relationship.start_date = this_monday - timedelta(weeks=4)
        for ago, count in weeks_done.items():
            day = datetime.combine(this_monday - timedelta(weeks=ago), datetime.min.time()) + timedelta(hours=10)
            for index in range(count):
                db.add(WorkoutSession(
                    student_id=relationship.student_id, relationship_id=relationship.id, routine_id=routine_id,
                    day_name="Día 1", modality="GYM", started_at=day + timedelta(days=index),
                    finished_at=day + timedelta(days=index, hours=1),
                ))
        db.commit()
    return relationship_id


def test_student_sees_streak_and_week_progress(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe@example.com", "TRAINER")
    student = register_and_login(api, "racha@example.com", "STUDENT")
    _relationship_with_history(api, sessions, trainer, "racha@example.com", {3: 1, 2: 1, 1: 2, 0: 1})

    body = api.get(STREAK, headers=student).json()

    assert body["has_routine"] is True
    assert body["weekly_target"] == 1
    assert body["current_weeks"] == 3
    assert body["max_weeks"] == 3
    assert body["this_week_sessions"] == 1
    assert body["week_start"] == monday(datetime.now(UTC).date()).isoformat()


def test_reset_sends_one_encouragement_notification(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe@example.com", "TRAINER")
    student = register_and_login(api, "corte@example.com", "STUDENT")
    _relationship_with_history(api, sessions, trainer, "corte@example.com", {3: 1, 2: 1})

    first = api.get(STREAK, headers=student).json()
    api.get(STREAK, headers=student)

    assert (first["current_weeks"], first["max_weeks"]) == (0, 2)
    with sessions() as db:
        user_id = db.scalar(select(User.id).where(User.email == "corte@example.com"))
        resets = list(db.scalars(select(Notification).where(
            Notification.recipient_id == user_id, Notification.type == "STREAK_RESET",
        )))
    assert len(resets) == 1
    assert resets[0].related_entity_id == (monday(datetime.now(UTC).date()) - timedelta(weeks=1)).isoformat()


def test_trainer_sees_the_streak_of_an_active_student(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe@example.com", "TRAINER")
    register_and_login(api, "visto@example.com", "STUDENT")
    relationship_id = _relationship_with_history(api, sessions, trainer, "visto@example.com", {2: 1, 1: 1})
    with sessions() as db:
        student_id = db.get(TrainingRelationship, relationship_id).student_id

    body = api.get(f"/api/v1/trainers/me/students/{student_id}/streak", headers=trainer).json()
    other = register_and_login(api, "otro@example.com", "TRAINER")

    assert (body["current_weeks"], body["max_weeks"]) == (2, 2)
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/streak", headers=other).status_code == 404
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/streak", headers=trainer).status_code == 404


def test_without_routine_there_is_no_streak_and_roles_are_enforced(client):
    api, _ = client
    student = register_and_login(api, "sinrutina@example.com", "STUDENT")
    trainer = register_and_login(api, "trainer_rpe@example.com", "TRAINER")

    body = api.get(STREAK, headers=student).json()

    assert body["has_routine"] is False
    assert body["current_weeks"] == 0
    assert api.get(STREAK, headers=trainer).status_code == 403
    assert api.get(STREAK).status_code == 401
