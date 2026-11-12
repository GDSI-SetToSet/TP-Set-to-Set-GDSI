from backend.tests.test_us61_body_map_pain_report_api import (
    REPORTS_PATH,
    TRAINER_STUDENTS_PATH,
    register_and_login,
    setup_test_environment,
)


def test_trainer_zone_history_includes_exercise_routine_day_and_muscle_group(client):
    api, sessions = client
    trainer = register_and_login(api, "entrenador_us28@example.com", "TRAINER")
    student = register_and_login(api, "alumno_us28@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_us28@example.com", "entrenador_us28@example.com")

    in_exercise = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "exercise_id": data["exercise_id"],
            "context": "IN_EXERCISE",
            "zones": [{"zone": "Shoulder", "intensity": "PAIN"}, {"zone": "Elbow", "intensity": "DISCOMFORT"}],
        },
    )
    post_session = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "context": "POST_SESSION",
            "zones": [{"zone": "Hip", "intensity": "DISCOMFORT"}],
        },
    )
    assert in_exercise.status_code == 201
    assert post_session.status_code == 201

    response = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data['student_profile_id']}/body-map-reports/by-zone",
        headers=trainer,
    )

    assert response.status_code == 200
    items = {item["zone"]: item for item in response.json()}
    assert set(items) == {"Shoulder", "Elbow", "Hip"}
    assert items["Shoulder"]["exercise_muscle_group"] == "Pecho"
    assert items["Shoulder"]["exercise_name"]
    assert items["Shoulder"]["session_day_name"]
    assert items["Elbow"]["intensity"] == "DISCOMFORT"
    assert items["Hip"]["exercise_muscle_group"] is None
    assert items["Hip"]["exercise_name"] is None
    assert items["Hip"]["session_day_name"] == items["Shoulder"]["session_day_name"]


def test_student_zone_history_also_exposes_muscle_group(client):
    api, sessions = client
    student = register_and_login(api, "alumno_us28_self@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_us28_self@example.com")
    api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "exercise_id": data["exercise_id"],
            "context": "IN_EXERCISE",
            "zones": [{"zone": "Knee", "intensity": "PAIN"}],
        },
    )

    history = api.get("/api/v1/students/me/body-map-reports/by-zone", headers=student).json()

    assert history[0]["exercise_muscle_group"] == "Pecho"
