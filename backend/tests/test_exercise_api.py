import pytest
from sqlalchemy import select

from backend.src.models.exercise import Exercise

EXERCISES_PATH = "/api/v1/exercises"
REQUIRED_MESSAGE = "Este campo es obligatorio"
INVALID_VIDEO_MESSAGE = (
    "Plataforma no soportada o link inválido. Solo se permite YouTube, Vimeo o Google Drive."
)
VALID_EXERCISE = {
    "name": "Sentadilla búlgara",
    "description": "Sentadilla unilateral con el pie trasero elevado",
    "category": "FUERZA",
    "target_muscle_group": "Cuádriceps",
    "equipment_needed": "Banco y mancuernas",
}


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_exercise(api, headers, **overrides) -> dict:
    response = api.post(EXERCISES_PATH, headers=headers, json={**VALID_EXERCISE, **overrides})
    assert response.status_code == 201
    return response.json()


def test_create_exercise_with_required_fields(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")

    exercise = create_exercise(api, trainer)

    assert exercise["name"] == "Sentadilla búlgara"
    assert exercise["category"] == "FUERZA"
    assert exercise["has_no_materials_alternative"] is False
    assert exercise["technical_cues"] is None
    assert exercise["breathing_cues"] is None
    assert exercise["video_url"] is None
    assert exercise["video_platform"] == "NONE"
    assert api.get(f"{EXERCISES_PATH}/{exercise['id']}", headers=trainer).json() == exercise


@pytest.mark.parametrize(
    ("video_url", "video_platform", "normalized_url"),
    [
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "YOUTUBE",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        (
            "https://vimeo.com/123456789",
            "VIMEO",
            "https://player.vimeo.com/video/123456789",
        ),
        (
            "https://drive.google.com/file/d/file_id-123/view?usp=sharing",
            "GOOGLE_DRIVE",
            "https://drive.google.com/file/d/file_id-123/preview",
        ),
    ],
)
def test_create_exercise_normalizes_supported_video_urls(
    client, video_url, video_platform, normalized_url
):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")

    exercise = create_exercise(api, trainer, video_url=video_url)

    assert exercise["video_platform"] == video_platform
    assert exercise["video_url"] == normalized_url


@pytest.mark.parametrize(
    "video_url",
    [
        "https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ",
        "https://vimeo.example/123456789",
        "https://example.com/video.mp4",
        "https://youtube.com/watch?v=short",
    ],
)
def test_create_exercise_rejects_invalid_video_urls(client, video_url):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")

    response = api.post(EXERCISES_PATH, headers=trainer, json={**VALID_EXERCISE, "video_url": video_url})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"] == [{"field": "video_url", "message": INVALID_VIDEO_MESSAGE}]
    assert api.get(EXERCISES_PATH, headers=trainer).json() == []


def test_update_exercise_replaces_and_removes_video(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    exercise = create_exercise(api, trainer, video_url="https://youtu.be/dQw4w9WgXcQ")
    path = f"{EXERCISES_PATH}/{exercise['id']}"

    replaced = api.put(
        path,
        headers=trainer,
        json={**VALID_EXERCISE, "video_url": "https://vimeo.com/123456789"},
    )

    assert replaced.status_code == 200
    assert replaced.json()["video_platform"] == "VIMEO"
    assert replaced.json()["video_url"] == "https://player.vimeo.com/video/123456789"

    removed = api.put(path, headers=trainer, json={**VALID_EXERCISE, "video_url": None})

    assert removed.status_code == 200
    assert removed.json()["video_url"] is None
    assert removed.json()["video_platform"] == "NONE"


def test_create_update_and_remove_technical_and_breathing_cues(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")

    exercise = create_exercise(
        api,
        trainer,
        technical_cues="  Espalda neutra y rodillas alineadas.  ",
        breathing_cues="  Inhalá al bajar y exhalá al subir.  ",
    )

    assert exercise["technical_cues"] == "Espalda neutra y rodillas alineadas."
    assert exercise["breathing_cues"] == "Inhalá al bajar y exhalá al subir."

    updated = api.put(
        f"{EXERCISES_PATH}/{exercise['id']}",
        headers=trainer,
        json={**VALID_EXERCISE, "technical_cues": "  ", "breathing_cues": None},
    )

    assert updated.status_code == 200
    assert updated.json()["technical_cues"] is None
    assert updated.json()["breathing_cues"] is None


@pytest.mark.parametrize("field", ["technical_cues", "breathing_cues"])
def test_exercise_rejects_cues_over_maximum_length(client, field):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")

    response = api.post(EXERCISES_PATH, headers=trainer, json={**VALID_EXERCISE, field: "x" * 2001})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field


@pytest.mark.parametrize("field", ["name", "description", "category", "target_muscle_group", "equipment_needed"])
def test_create_exercise_requires_every_field(client, field):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    payload = {key: value for key, value in VALID_EXERCISE.items() if key != field}

    response = api.post(EXERCISES_PATH, headers=trainer, json=payload)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"] == [{"field": field, "message": REQUIRED_MESSAGE}]
    assert api.get(EXERCISES_PATH, headers=trainer).json() == []


def test_create_exercise_rejects_blank_and_invalid_values(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")

    blank = api.post(EXERCISES_PATH, headers=trainer, json={**VALID_EXERCISE, "name": "   "})
    assert blank.status_code == 422
    assert blank.json()["errors"] == [{"field": "name", "message": REQUIRED_MESSAGE}]

    category = api.post(EXERCISES_PATH, headers=trainer, json={**VALID_EXERCISE, "category": "YOGA"})
    assert category.status_code == 422
    assert category.json()["errors"][0]["field"] == "category"

    too_long = api.post(EXERCISES_PATH, headers=trainer, json={**VALID_EXERCISE, "name": "x" * 151})
    assert too_long.status_code == 422
    assert too_long.json()["errors"][0]["field"] == "name"


def test_list_filters_by_muscle_and_isolates_trainers(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    other = register_and_login(api, "other@example.com", "TRAINER")
    squat = create_exercise(api, trainer)
    press = create_exercise(api, trainer, name="Press plano", target_muscle_group="Pectoral")
    create_exercise(api, other, name="Ajeno")

    all_exercises = api.get(EXERCISES_PATH, headers=trainer).json()
    assert [item["id"] for item in all_exercises] == [press["id"], squat["id"]]

    filtered = api.get(EXERCISES_PATH, headers=trainer, params={"muscle_group": " pectoral "})
    assert [item["id"] for item in filtered.json()] == [press["id"]]

    assert api.get(EXERCISES_PATH, headers=trainer, params={"muscle_group": "Gemelos"}).json() == []


def test_update_exercise_replaces_data(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    exercise = create_exercise(api, trainer)

    response = api.put(
        f"{EXERCISES_PATH}/{exercise['id']}",
        headers=trainer,
        json={**VALID_EXERCISE, "category": "MOVILIDAD", "has_no_materials_alternative": True},
    )

    assert response.status_code == 200
    assert response.json()["category"] == "MOVILIDAD"
    assert response.json()["has_no_materials_alternative"] is True

    invalid = api.put(f"{EXERCISES_PATH}/{exercise['id']}", headers=trainer, json={"name": "Solo nombre"})
    assert invalid.status_code == 422
    assert api.get(f"{EXERCISES_PATH}/{exercise['id']}", headers=trainer).json()["name"] == VALID_EXERCISE["name"]


def test_delete_exercise_is_logical(client):
    api, session_factory = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    exercise = create_exercise(api, trainer)
    path = f"{EXERCISES_PATH}/{exercise['id']}"

    assert api.delete(path, headers=trainer).status_code == 204

    assert api.get(EXERCISES_PATH, headers=trainer).json() == []
    assert api.get(path, headers=trainer).status_code == 404
    assert api.put(path, headers=trainer, json=VALID_EXERCISE).status_code == 404
    assert api.delete(path, headers=trainer).status_code == 404
    with session_factory() as db:
        stored = db.scalar(select(Exercise).where(Exercise.id == exercise["id"]))
        assert stored is not None
        assert stored.deleted_at is not None


def test_exercises_of_other_trainers_do_not_exist(client):
    api, _ = client
    trainer = register_and_login(api, "coach@example.com", "TRAINER")
    other = register_and_login(api, "other@example.com", "TRAINER")
    path = f"{EXERCISES_PATH}/{create_exercise(api, trainer)['id']}"

    assert api.get(path, headers=other).status_code == 404
    assert api.put(path, headers=other, json=VALID_EXERCISE).status_code == 404
    assert api.delete(path, headers=other).status_code == 404
    assert api.get(path, headers=trainer).status_code == 200


def test_exercises_require_trainer_role(client):
    api, _ = client
    student = register_and_login(api, "student@example.com", "STUDENT")

    assert api.get(EXERCISES_PATH, headers=student).status_code == 403
    assert api.post(EXERCISES_PATH, headers=student, json=VALID_EXERCISE).status_code == 403
    assert api.get(EXERCISES_PATH).status_code == 401
