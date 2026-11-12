from datetime import UTC, datetime, timedelta

from backend.src.services import abandonment_risk_service, routine_template_service
from backend.src.services.abandonment_risk_service import (
    REASON_INACTIVE_TWO_WEEKS,
    REASON_MISSED_TRAININGS,
    evaluate_risk,
)
from backend.tests.test_workout_session_api import (
    ASSIGNED_PATH,
    create_assigned_routine,
    link_student,
    register_and_login,
)

RISK_PATH = "/api/v1/trainers/me/abandonment-risk"
NOTIFICATIONS_PATH = "/api/v1/trainers/me/notifications"


def test_evaluate_risk_uses_whichever_threshold_comes_first():
    # 3 entrenamientos por semana: 5 sin reportar a los 12 días, antes de las 2 semanas.
    assert evaluate_risk(11, 3) == (False, None, 4)
    assert evaluate_risk(12, 3) == (True, REASON_MISSED_TRAININGS, 5)
    # 1 entrenamiento por semana: las 2 semanas llegan antes que 5 entrenamientos.
    assert evaluate_risk(13, 1) == (False, None, 1)
    assert evaluate_risk(14, 1) == (True, REASON_INACTIVE_TWO_WEEKS, 2)
    # Sin rutina no se esperan entrenamientos.
    assert evaluate_risk(60, 0) == (False, None, 0)


def at(monkeypatch, moment: datetime) -> None:
    monkeypatch.setattr(abandonment_risk_service, "utc_now", lambda: moment.replace(tzinfo=None))


def risk_by_student(api, trainer) -> dict[str, dict]:
    response = api.get(RISK_PATH, headers=trainer)
    assert response.status_code == 200
    return {item["student_name"]: item for item in response.json()}


def abandonment_notifications(api, trainer) -> list[dict]:
    items = api.get(NOTIFICATIONS_PATH, headers=trainer, params={"limit": 100}).json()["items"]
    return [item for item in items if item["type"] == "ABANDONMENT_RISK"]


def test_alerts_once_per_inactivity_period_and_sorts_risky_students_first(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    active = register_and_login(api, "active@example.com", "STUDENT")
    register_and_login(api, "idle@example.com", "STUDENT")
    register_and_login(api, "no-routine@example.com", "STUDENT")
    create_assigned_routine(api, sessions, trainer, "active@example.com")
    create_assigned_routine(api, sessions, trainer, "idle@example.com")
    link_student(sessions, "trainer@example.com", "no-routine@example.com")
    today = datetime.now(UTC)

    at(monkeypatch, today + timedelta(days=3))
    early = api.get(RISK_PATH, headers=trainer).json()
    assert len(early) == 3
    assert not any(item["at_risk"] for item in early)
    assert abandonment_notifications(api, trainer) == []

    # Pasadas 2 semanas, el alumno activo reporta un entrenamiento y el otro no.
    later = today + timedelta(days=15)
    monkeypatch.setattr(routine_template_service, "utc_now", lambda: later)
    session = api.post(f"{ASSIGNED_PATH}/workout-sessions", headers=active, json={"day_name": "Día 1"}).json()
    assert api.post(f"{ASSIGNED_PATH}/workout-sessions/{session['id']}/finish", headers=active).status_code == 200

    at(monkeypatch, later)
    response = api.get(RISK_PATH, headers=trainer).json()
    assert response[0]["at_risk"] is True
    assert [item["at_risk"] for item in response] == [True, False, False]
    risk = {item["relationship_id"]: item for item in response}
    idle = response[0]
    assert idle["reason"] == REASON_INACTIVE_TWO_WEEKS
    assert idle["days_without_report"] == 15
    assert idle["weekly_trainings"] == 1
    assert idle["last_report_at"] is None
    reporting = next(item for item in risk.values() if item["last_report_at"] is not None)
    assert reporting["days_without_report"] == 0
    no_routine = next(item for item in risk.values() if item["weekly_trainings"] == 0)
    assert no_routine["at_risk"] is False

    alerts = abandonment_notifications(api, trainer)
    assert len(alerts) == 1
    assert alerts[0]["related_student_id"] == idle["student_id"]
    assert alerts[0]["related_entity_id"] == idle["relationship_id"]
    assert "no reporta entrenamientos hace 15 días" in alerts[0]["message"]

    # Consultar de nuevo no duplica la alerta del mismo período.
    api.get(RISK_PATH, headers=trainer)
    assert len(abandonment_notifications(api, trainer)) == 1

    # Dos semanas después del último reporte, el alumno que había entrenado también entra en riesgo.
    at(monkeypatch, later + timedelta(days=14))
    assert len(abandonment_notifications(api, trainer)) == 2
    assert [item["at_risk"] for item in api.get(RISK_PATH, headers=trainer).json()] == [True, True, False]


def test_notifications_endpoint_generates_alert_and_risk_is_private(client, monkeypatch):
    api, sessions = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")
    register_and_login(api, "idle@example.com", "STUDENT")
    create_assigned_routine(api, sessions, trainer, "idle@example.com")
    other_trainer = register_and_login(api, "other-trainer@example.com", "TRAINER")
    student = register_and_login(api, "student-only@example.com", "STUDENT")

    at(monkeypatch, datetime.now(UTC) + timedelta(days=20))

    assert len(abandonment_notifications(api, trainer)) == 1
    assert api.get(RISK_PATH, headers=other_trainer).json() == []
    assert abandonment_notifications(api, other_trainer) == []
    assert api.get(RISK_PATH, headers=student).status_code in (403, 404)
    assert api.get(RISK_PATH).status_code == 401


def test_notifications_still_load_if_risk_evaluation_fails(client, monkeypatch):
    api, _ = client
    trainer = register_and_login(api, "trainer@example.com", "TRAINER")

    def boom(*_args, **_kwargs):
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr("backend.src.api.v1.discovery.list_abandonment_risk", boom)

    response = api.get(NOTIFICATIONS_PATH, headers=trainer)
    assert response.status_code == 200
