from datetime import UTC, datetime
from decimal import Decimal

from fastapi import status
from sqlalchemy import select

from backend.src.models import ProtectedZone
from backend.src.models.notification import Notification
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.protected_zone import ProtectedZonesUpdate

URL = "/api/v1/students/me/protected-zones"


def register_and_login(test_client, email, role):
    test_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "role": role},
    )
    token = test_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def link_trainer_to_student(session_factory, trainer_email: str, student_email: str, relationship_status="ACTIVE"):
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))
        trainer_profile = trainer_user.trainer_profile
        if trainer_profile is None:
            trainer_profile = TrainerProfile(
                user_id=trainer_user.id,
                status="PUBLISHED",
                max_students=10,
                created_at=now,
                updated_at=now,
            )
            db.add(trainer_profile)
            db.flush()
        student_profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == student_user.id)
        )
        if student_profile is None:
            student_profile = StudentProfile(
                user_id=student_user.id,
                status="DRAFT",
                created_at=now,
                updated_at=now,
            )
            db.add(student_profile)
            db.flush()
        plan = TrainingPlan(
            trainer_id=trainer_profile.id,
            title="Plan de entrenamiento",
            monthly_price=Decimal(10000),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.flush()
        db.add(
            TrainingRelationship(
                student_id=student_profile.id,
                trainer_id=trainer_profile.id,
                plan_id=plan.id,
                agreed_monthly_price=Decimal(10000),
                agreed_currency="ARS",
                status=relationship_status,
                start_date=now.date(),
            )
        )
        db.commit()
        return student_profile.id


def test_protected_zones_are_saved_and_returned(client, student_token_headers):
    test_client, session_factory = client

    response = test_client.put(
        URL,
        headers=student_token_headers,
        json={"zones": ["  Left knee ", "Lower back"]},
    )

    assert response.status_code == status.HTTP_200_OK
    assert [zone["body_area"] for zone in response.json()["zones"]] == ["Left knee", "Lower back"]
    with session_factory() as db:
        assert db.query(ProtectedZone).count() == 2


def test_removing_protected_zone_removes_its_restriction(client, student_token_headers):
    test_client, session_factory = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee", "Shoulder"]})

    response = test_client.put(URL, headers=student_token_headers, json={"zones": ["Shoulder"]})

    assert response.status_code == status.HTTP_200_OK
    assert [zone["body_area"] for zone in response.json()["zones"]] == ["Shoulder"]
    with session_factory() as db:
        assert [zone.body_area for zone in db.query(ProtectedZone).all()] == ["Shoulder"]


def test_empty_zone_list_clears_all_zones(client, student_token_headers):
    test_client, session_factory = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee"]})

    response = test_client.put(URL, headers=student_token_headers, json={"zones": []})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["zones"] == []
    with session_factory() as db:
        assert db.query(ProtectedZone).count() == 0


def test_protected_zones_are_private_to_the_owning_student(client, student_token_headers):
    test_client, _ = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee"]})
    other_student = register_and_login(test_client, "another-student@example.com", "STUDENT")
    trainer = register_and_login(test_client, "trainer@example.com", "TRAINER")

    assert test_client.get(URL, headers=other_student).json()["zones"] == []
    assert test_client.get(URL, headers=trainer).status_code == status.HTTP_403_FORBIDDEN
    assert test_client.put(URL, headers=trainer, json={"zones": []}).status_code == status.HTTP_403_FORBIDDEN


def test_changed_protected_zones_notify_only_trainers_with_active_relationship(client):
    test_client, session_factory = client
    student = register_and_login(test_client, "zones_student@example.com", "STUDENT")
    active_trainer = register_and_login(test_client, "zones_active_trainer@example.com", "TRAINER")
    unrelated_trainer = register_and_login(test_client, "zones_unrelated_trainer@example.com", "TRAINER")
    inactive_trainer = register_and_login(test_client, "zones_inactive_trainer@example.com", "TRAINER")

    profile_id = link_trainer_to_student(
        session_factory, "zones_active_trainer@example.com", "zones_student@example.com"
    )
    link_trainer_to_student(
        session_factory,
        "zones_inactive_trainer@example.com",
        "zones_student@example.com",
        relationship_status="ENDED",
    )
    with session_factory() as db:
        profile = db.get(StudentProfile, profile_id)
        profile.first_name = "Ana"
        profile.last_name = "Pérez"
        db.commit()

    update = test_client.put(URL, headers=student, json={"zones": ["Shoulder", "Knee"]})

    assert update.status_code == status.HTTP_200_OK
    active_notifications = test_client.get(
        "/api/v1/trainers/me/notifications", headers=active_trainer
    ).json()
    assert active_notifications["total"] == 1
    notification = active_notifications["items"][0]
    assert notification["type"] == "PROTECTED_ZONES_UPDATED"
    assert notification["title"] == "Zonas a proteger actualizadas"
    assert notification["message"] == (
        "Ana Pérez actualizó sus zonas a proteger. Revisá si es necesario adaptar algún "
        "ejercicio de su rutina a sus nuevas limitaciones."
    )
    assert notification["related_student_id"] == profile_id
    assert "Knee" not in notification["message"]
    assert test_client.get(
        "/api/v1/trainers/me/notifications", headers=unrelated_trainer
    ).json()["total"] == 0
    assert test_client.get(
        "/api/v1/trainers/me/notifications", headers=inactive_trainer
    ).json()["total"] == 0
    with session_factory() as db:
        assert db.query(Notification).count() == 1


def test_saving_same_protected_zones_does_not_create_duplicate_notification(client):
    test_client, session_factory = client
    student = register_and_login(test_client, "zones_unchanged_student@example.com", "STUDENT")
    trainer = register_and_login(test_client, "zones_unchanged_trainer@example.com", "TRAINER")
    link_trainer_to_student(
        session_factory, "zones_unchanged_trainer@example.com", "zones_unchanged_student@example.com"
    )

    first = test_client.put(URL, headers=student, json={"zones": ["Knee", "Shoulder"]})
    unchanged = test_client.put(URL, headers=student, json={"zones": ["Shoulder", "Knee"]})

    assert first.status_code == status.HTTP_200_OK
    assert unchanged.status_code == status.HTTP_200_OK
    notifications = test_client.get("/api/v1/trainers/me/notifications", headers=trainer).json()
    assert notifications["total"] == 1
    assert notifications["unread_count"] == 1
    with session_factory() as db:
        assert db.query(Notification).count() == 1


def test_new_protected_zone_update_notifies_active_trainer_again(client):
    test_client, session_factory = client
    student = register_and_login(test_client, "zones_changed_student@example.com", "STUDENT")
    trainer = register_and_login(test_client, "zones_changed_trainer@example.com", "TRAINER")
    link_trainer_to_student(
        session_factory, "zones_changed_trainer@example.com", "zones_changed_student@example.com"
    )

    assert test_client.put(URL, headers=student, json={"zones": ["Knee"]}).status_code == 200
    changed = test_client.put(URL, headers=student, json={"zones": ["Knee", "Shoulder"]})

    assert changed.status_code == status.HTTP_200_OK
    notifications = test_client.get("/api/v1/trainers/me/notifications", headers=trainer).json()
    assert notifications["total"] == 2
    assert all(item["type"] == "PROTECTED_ZONES_UPDATED" for item in notifications["items"])


def test_student_without_active_trainers_can_update_zones_without_notifications(client, student_token_headers):
    test_client, session_factory = client

    response = test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee"]})

    assert response.status_code == status.HTTP_200_OK
    with session_factory() as db:
        assert db.query(Notification).count() == 0


def test_trainer_cannot_update_a_students_protected_zones(client):
    test_client, session_factory = client
    trainer = register_and_login(test_client, "zones_forbidden_trainer@example.com", "TRAINER")

    response = test_client.put(URL, headers=trainer, json={"zones": ["Knee"]})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    with session_factory() as db:
        assert db.query(ProtectedZone).count() == 0
        assert db.query(Notification).count() == 0


def test_invalid_zone_names_are_rejected_without_changing_saved_zones(client, student_token_headers):
    test_client, session_factory = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee"]})

    for zones in ([" "], ["Knee", " knee "], ["x" * 81], ["zone"] * 21):
        response = test_client.put(URL, headers=student_token_headers, json={"zones": zones})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    with session_factory() as db:
        assert [zone.body_area for zone in db.query(ProtectedZone).all()] == ["Knee"]


def test_protected_zone_schema_normalizes_whitespace_and_rejects_case_insensitive_duplicates():
    assert ProtectedZonesUpdate(zones=["  Left knee  "]).zones == ["Left knee"]
