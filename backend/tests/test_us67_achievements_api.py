"""US-67: logros y medallas (catálogo del MVP), celebración y felicitación del entrenador."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.src.models.achievement import StudentAchievement
from backend.src.models.notification import Notification
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.src.services.achievement_service import CATALOG
from backend.src.services.streak_service import monday, streak_reached_on
from backend.tests.test_us60_rpe_api import (
    ASSIGNED_PATH,
    register_and_login,
    setup_routine_and_assignment,
)

ACHIEVEMENTS = "/api/v1/students/me/achievements"


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture
def setup(client):
    api, sessions = client
    trainer = register_and_login(api, "trainer_rpe@example.com", "TRAINER")
    student = register_and_login(api, "logros@example.com", "STUDENT")
    exercise_id, relationship_id, routine_id = setup_routine_and_assignment(api, sessions, trainer, "logros@example.com")
    with sessions() as db:
        student_id = db.get(TrainingRelationship, relationship_id).student_id
    return api, sessions, trainer, student, exercise_id, relationship_id, routine_id, student_id


def add_history(
    sessions,
    relationship_id,
    routine_id,
    exercise_id,
    days_ago: list[int],
    weights: list[int] | None = None,
    reps: list[str] | None = None,
):
    """Sesiones finalizadas hace N días; con `weights`, una serie por sesión con ese peso."""
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        for index, ago in enumerate(days_ago):
            start = now() - timedelta(days=ago, hours=2)
            session = WorkoutSession(
                student_id=relationship.student_id, relationship_id=relationship.id, routine_id=routine_id,
                day_name="Día 1", modality="GYM", started_at=start, finished_at=start + timedelta(hours=1),
            )
            db.add(session)
            db.flush()
            if weights is not None:
                db.add(WorkoutSetLog(
                    student_id=relationship.student_id, relationship_id=relationship.id, routine_id=routine_id,
                    day_name="Día 1", exercise_id=exercise_id, exercise_name="Press militar", set_number=1,
                    reps_completed=reps[index] if reps is not None else "10",
                    weight_kg=Decimal(weights[index]) if weights[index] is not None else None,
                    session_id=session.id,
                    recorded_at=start + timedelta(minutes=10),
                ))
        db.commit()


def codes(body: dict, key: str = "unlocked") -> set[str]:
    return {item["code"] for item in body[key]}


def finish_session(api, student) -> dict:
    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    finished = api.post(f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish", headers=student, json={})
    assert finished.status_code == 200
    return session


def notifications(sessions, email: str, kind: str) -> list[Notification]:
    with sessions() as db:
        user_id = db.scalar(select(User.id).where(User.email == email))
        return list(db.scalars(select(Notification).where(Notification.recipient_id == user_id, Notification.type == kind)))


# Escenario 1 y 2: desbloqueo al finalizar la sesión ----------------------------------------


def test_first_session_unlocks_on_finish_with_celebration_and_notifications(setup):
    api, sessions, _, student, *_ = setup
    assert api.get(ACHIEVEMENTS, headers=student).json()["unlocked"] == []

    finish_session(api, student)

    body = api.get(ACHIEVEMENTS, headers=student).json()
    assert codes(body) == {"FIRST_SESSION"}
    [first] = body["unlocked"]
    assert first["title"] == "Primera sesión"
    assert first["retroactive"] is False
    assert first["pending_celebration"] is True
    assert first["unlocked_at"].startswith(now().date().isoformat())
    [student_notice] = notifications(sessions, "logros@example.com", "ACHIEVEMENT_UNLOCKED")
    assert "Primera sesión" in student_notice.title
    [trainer_notice] = notifications(sessions, "trainer_rpe@example.com", "ACHIEVEMENT_UNLOCKED")
    assert "desbloqueó un logro: Primera sesión" in trainer_notice.title
    assert trainer_notice.related_entity_id == first["id"]
    assert trainer_notice.related_student_id


def test_celebration_is_acknowledged_once(setup):
    api, _, _, student, *_ = setup
    finish_session(api, student)
    [item] = api.get(ACHIEVEMENTS, headers=student).json()["unlocked"]

    assert api.post(f"{ACHIEVEMENTS}/{item['id']}/celebrated", headers=student).status_code == 204
    assert api.post(f"{ACHIEVEMENTS}/{item['id']}/celebrated", headers=student).status_code == 204

    assert api.get(ACHIEVEMENTS, headers=student).json()["unlocked"][0]["pending_celebration"] is False
    assert api.post(f"{ACHIEVEMENTS}/no-existe/celebrated", headers=student).status_code == 404


def test_tenth_session_unlocks_a_fresh_achievement_and_earlier_ones_are_retroactive(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    add_history(sessions, relationship_id, routine_id, exercise_id, days_ago=list(range(40, 31, -1)))  # 9 sesiones previas

    finish_session(api, student)

    items = {item["code"]: item for item in api.get(ACHIEVEMENTS, headers=student).json()["unlocked"]}
    assert set(items) == {"FIRST_SESSION", "TEN_SESSIONS"}
    assert items["TEN_SESSIONS"]["retroactive"] is False
    assert items["TEN_SESSIONS"]["pending_celebration"] is True
    # La primera sesión se cumplió antes de la funcionalidad: fecha real, sin celebrar ni avisar.
    assert items["FIRST_SESSION"]["retroactive"] is True
    assert items["FIRST_SESSION"]["pending_celebration"] is False
    assert items["FIRST_SESSION"]["unlocked_at"].startswith((now() - timedelta(days=40, hours=1)).date().isoformat())
    titles = [n.title for n in notifications(sessions, "logros@example.com", "ACHIEVEMENT_UNLOCKED")]
    assert titles == ["¡Desbloqueaste un logro: 10 sesiones!"]
    assert len(notifications(sessions, "trainer_rpe@example.com", "ACHIEVEMENT_UNLOCKED")) == 1


def test_personal_record_achievements_use_strictly_greater_weights(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    # 20 (marca inicial: no es récord), 20 (igual: no es récord), 25, 30, 35, 40, 45 → 5 récords reales.
    add_history(
        sessions, relationship_id, routine_id, exercise_id,
        [35, 30, 25, 20, 15, 10, 5], [20, 20, 25, 30, 35, 40, 45],
    )

    body = api.get(ACHIEVEMENTS, headers=student).json()

    assert {"FIRST_PR", "FIVE_PRS"} <= codes(body)
    assert all(item["retroactive"] for item in body["unlocked"])
    assert notifications(sessions, "trainer_rpe@example.com", "ACHIEVEMENT_UNLOCKED") == []


def test_first_load_is_not_a_personal_record(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    add_history(sessions, relationship_id, routine_id, exercise_id, [10, 5], [20, 20], ["8", "8"])

    body = api.get(ACHIEVEMENTS, headers=student).json()

    assert codes(body) == {"FIRST_SESSION"}
    locked = {item["code"]: item for item in body["locked"]}
    assert (locked["FIRST_PR"]["current"], locked["FIRST_PR"]["target"]) == (0, 1)


def test_same_weight_with_more_reps_counts_as_personal_record(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    add_history(sessions, relationship_id, routine_id, exercise_id, [10, 5], [20, 20], ["8", "10"])

    body = api.get(ACHIEVEMENTS, headers=student).json()

    assert codes(body) == {"FIRST_SESSION", "FIRST_PR"}
    pr_item = next(item for item in body["unlocked"] if item["code"] == "FIRST_PR")
    assert pr_item["unlocked_at"].startswith((now() - timedelta(days=5, hours=2)).date().isoformat())


def test_live_pr_unlock_on_session_finish_respects_previous_mark(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    add_history(sessions, relationship_id, routine_id, exercise_id, [7], [40], ["8"])
    assert codes(api.get(ACHIEVEMENTS, headers=student).json()) == {"FIRST_SESSION"}

    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=student, json={"day_name": "Día 1"}).json()
    logged = api.post(
        f"{ASSIGNED_PATH}/workout-logs",
        headers=student,
        json={
            "day_name": "Día 1",
            "exercise_id": exercise_id,
            "set_number": 1,
            "reps_completed": "10",
            "weight_kg": 40,
            "session_id": session["id"],
        },
    )
    assert logged.status_code == 201
    finished = api.post(f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish", headers=student, json={})
    assert finished.status_code == 200

    items = {item["code"]: item for item in api.get(ACHIEVEMENTS, headers=student).json()["unlocked"]}
    assert "FIRST_PR" in items
    assert items["FIRST_PR"]["retroactive"] is False
    assert items["FIRST_PR"]["pending_celebration"] is True


def test_locked_achievements_show_progress(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    # 20 (inicial: 0 PR), 20 (igual: 0 PR), 25 (supera: 1 PR).
    add_history(sessions, relationship_id, routine_id, exercise_id, [9, 8, 7], [20, 20, 25])

    body = api.get(ACHIEVEMENTS, headers=student).json()

    locked = {item["code"]: item for item in body["locked"]}
    assert codes(body) == {"FIRST_SESSION", "FIRST_PR"}
    assert (locked["TEN_SESSIONS"]["current"], locked["TEN_SESSIONS"]["target"]) == (3, 10)
    assert (locked["FIVE_PRS"]["current"], locked["FIVE_PRS"]["target"]) == (1, 5)
    assert set(locked) == {item.code for item in CATALOG} - codes(body)


def test_achievements_are_never_lost_or_duplicated(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    add_history(sessions, relationship_id, routine_id, exercise_id, [3])

    first = api.get(ACHIEVEMENTS, headers=student).json()
    with sessions() as db:
        for session in db.scalars(select(WorkoutSession)):
            session.finished_at = None  # aunque el historial cambie, el logro desbloqueado queda
        db.commit()
    second = api.get(ACHIEVEMENTS, headers=student).json()

    assert codes(first) == codes(second) == {"FIRST_SESSION"}
    with sessions() as db:
        assert len(list(db.scalars(select(StudentAchievement)))) == 1


# Racha de 4 semanas ----------------------------------------------------------------------


def test_streak_reached_on_returns_the_monday_after_the_fourth_met_week():
    from datetime import date

    monday_now = date(2026, 11, 16)
    done = {monday_now - timedelta(weeks=n): 3 for n in (5, 4, 3, 2)}
    assert streak_reached_on(3, monday_now - timedelta(weeks=5), done, monday_now, 4) == monday_now - timedelta(weeks=1)
    done[monday_now - timedelta(weeks=3)] = 2  # semana incumplida: la racha no llega a 4
    assert streak_reached_on(3, monday_now - timedelta(weeks=5), done, monday_now, 4) is None
    assert streak_reached_on(0, monday_now, {}, monday_now, 4) is None


def test_four_week_streak_unlocks_and_celebrates_when_the_week_ends(setup):
    api, sessions, _, student, exercise_id, relationship_id, routine_id, _ = setup
    this_monday = monday(now().date())
    with sessions() as db:
        relationship = db.get(TrainingRelationship, relationship_id)
        relationship.routine_assigned_at = datetime.combine(this_monday - timedelta(weeks=4), datetime.min.time())
        db.commit()
    # Rutina de 1 día: una sesión por semana, las 4 semanas anteriores.
    add_history(sessions, relationship_id, routine_id, exercise_id, days_ago=[(now().date() - (this_monday - timedelta(weeks=n))).days - 1 for n in (4, 3, 2, 1)])

    body = api.get(ACHIEVEMENTS, headers=student).json()

    items = {item["code"]: item for item in body["unlocked"]}
    assert "STREAK_4_WEEKS" in items
    streak = items["STREAK_4_WEEKS"]
    assert streak["unlocked_at"].startswith(this_monday.isoformat())
    assert streak["retroactive"] is False  # se completó esta semana
    assert streak["pending_celebration"] is True
    assert any("Racha de 4 semanas" in n.title for n in notifications(sessions, "trainer_rpe@example.com", "ACHIEVEMENT_UNLOCKED"))


# Escenario 4: felicitación ---------------------------------------------------------------


def test_trainer_congratulates_and_student_sees_it_once(setup):
    api, sessions, trainer, student, *_ , student_id = setup
    finish_session(api, student)
    [item] = api.get(ACHIEVEMENTS, headers=student).json()["unlocked"]
    listing = api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=trainer)
    assert listing.status_code == 200
    assert codes(listing.json()) == {"FIRST_SESSION"}

    response = api.post(
        f"/api/v1/trainers/me/achievements/{item['id']}/congratulation",
        json={"message": "  ¡Excelente arranque!  "},
        headers=trainer,
    )

    assert response.status_code == 201
    assert response.json()["congratulation"]["message"] == "¡Excelente arranque!"
    assert response.json()["congratulation"]["trainer_name"] == "trainer_rpe@example.com"  # sin nombre cargado: usa el email
    [notice] = notifications(sessions, "logros@example.com", "CONGRATULATION")
    assert "te felicitó" in notice.title
    shown = api.get(ACHIEVEMENTS, headers=student).json()["unlocked"][0]["congratulation"]
    assert shown["message"] == "¡Excelente arranque!"
    assert shown["seen_at"] is None
    assert api.post(f"{ACHIEVEMENTS}/{item['id']}/congratulation/seen", headers=student).status_code == 204
    assert api.get(ACHIEVEMENTS, headers=student).json()["unlocked"][0]["congratulation"]["seen_at"] is not None
    again = api.post(f"/api/v1/trainers/me/achievements/{item['id']}/congratulation", json={"message": "Otra"}, headers=trainer)
    assert again.status_code == 409


@pytest.mark.parametrize("body", [{}, {"message": ""}, {"message": "   "}, {"message": "x" * 301}])
def test_congratulation_is_validated(setup, body):
    api, _, trainer, student, *_ = setup
    finish_session(api, student)
    [item] = api.get(ACHIEVEMENTS, headers=student).json()["unlocked"]

    response = api.post(f"/api/v1/trainers/me/achievements/{item['id']}/congratulation", json=body, headers=trainer)

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "message", "message": "Escribí la felicitación (hasta 300 caracteres)."}]


def test_authorization_and_privacy(setup):
    api, _, trainer, student, *_, student_id = setup
    finish_session(api, student)
    [item] = api.get(ACHIEVEMENTS, headers=student).json()["unlocked"]
    other_trainer = register_and_login(api, "otro@example.com", "TRAINER")
    other_student = register_and_login(api, "otra@example.com", "STUDENT")
    congratulate = f"/api/v1/trainers/me/achievements/{item['id']}/congratulation"

    assert api.get(ACHIEVEMENTS, headers=trainer).status_code == 403
    assert api.get(ACHIEVEMENTS).status_code == 401
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=other_trainer).status_code == 404
    assert api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=student).status_code == 403
    assert api.post(congratulate, json={"message": "Hola"}, headers=other_trainer).status_code == 404
    assert api.post(congratulate, json={"message": "Hola"}, headers=student).status_code == 403
    assert api.post("/api/v1/trainers/me/achievements/no-existe/congratulation", json={"message": "Hola"}, headers=trainer).status_code == 404
    assert api.post(f"{ACHIEVEMENTS}/{item['id']}/celebrated", headers=other_student).status_code == 404
    assert api.post(f"{ACHIEVEMENTS}/{item['id']}/congratulation/seen", headers=other_student).status_code == 404
    assert api.post(f"{ACHIEVEMENTS}/{item['id']}/congratulation/seen", headers=student).status_code == 404  # sin felicitación
    assert api.get(ACHIEVEMENTS, headers=other_student).json()["unlocked"] == []


def test_ended_relationship_blocks_trainer_access(setup):
    api, sessions, trainer, student, _, relationship_id, _, student_id = setup
    finish_session(api, student)
    [item] = api.get(ACHIEVEMENTS, headers=student).json()["unlocked"]
    with sessions() as db:
        db.get(TrainingRelationship, relationship_id).status = "TERMINATED"
        db.commit()

    assert api.get(f"/api/v1/trainers/me/students/{student_id}/achievements", headers=trainer).status_code == 404
    assert api.post(f"/api/v1/trainers/me/achievements/{item['id']}/congratulation", json={"message": "Hola"}, headers=trainer).status_code == 404
    assert codes(api.get(ACHIEVEMENTS, headers=student).json()) == {"FIRST_SESSION"}  # el alumno conserva sus logros


def test_student_without_profile_sees_the_full_locked_catalog(client):
    api, _ = client
    student = register_and_login(api, "nuevo@example.com", "STUDENT")

    body = api.get(ACHIEVEMENTS, headers=student).json()

    assert body["unlocked"] == []
    assert len(body["locked"]) == len(CATALOG)
    assert all(item["current"] == 0 for item in body["locked"])
