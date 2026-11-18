from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession

STUDENTS_PATH = "/api/v1/trainers/me/students"
ASSIGNMENTS_PATH = "/api/v1/routine-templates/assignments"


def register_and_login(api, email: str, role: str) -> dict[str, str]:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    response = api.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_relationship(
    sessions,
    trainer_email: str,
    student_email: str,
    status: str = "ACTIVE",
    plan_title: str = "Plan Premium",
) -> tuple[str, str]:
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer_user = db.scalar(select(User).where(User.email == trainer_email))
        student_user = db.scalar(select(User).where(User.email == student_email))
        trainer = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == trainer_user.id))
        if trainer is None:
            trainer = TrainerProfile(
                user_id=trainer_user.id,
                full_name="Entrenador Principal",
                status="PUBLISHED",
                created_at=now,
                updated_at=now,
            )
        student = StudentProfile(
            user_id=student_user.id,
            first_name="Valeria",
            last_name="Alumna",
            birth_date=datetime(1990, 1, 1),
            contact_phone="+5491112345678",
            bio="Perfil de prueba",
            fitness_goals=["fuerza"],
            personal_motivation="Entrenar mejor",
            status="PUBLISHED",
            created_at=now,
            updated_at=now,
        )
        db.add_all([trainer, student])
        db.flush()
        student.protected_zones.append(ProtectedZone(body_area="Hombro derecho", created_at=now))
        plan = TrainingPlan(
            trainer_id=trainer.id,
            title=plan_title,
            description="Plan de prueba",
            monthly_price=Decimal("10000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.flush()
        relationship = TrainingRelationship(
            trainer_id=trainer.id,
            student_id=student.id,
            plan_id=plan.id,
            agreed_monthly_price=Decimal("12500.00"),
            agreed_currency="ARS",
            status=status,
            start_date=now.date(),
        )
        db.add(relationship)
        db.commit()
        return relationship.id, student.id


def test_lists_only_active_students_owned_by_trainer(client):
    api, sessions = client
    trainer_headers = register_and_login(api, "trainer@example.com", "TRAINER")
    register_and_login(api, "student-active@example.com", "STUDENT")
    register_and_login(api, "student-ended@example.com", "STUDENT")
    create_relationship(sessions, "trainer@example.com", "student-active@example.com")
    create_relationship(sessions, "trainer@example.com", "student-ended@example.com", status="TERMINATED")

    response = api.get(STUDENTS_PATH, headers=trainer_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["full_name"] == "Valeria Alumna"
    assert response.json()[0]["package_title"] == "Plan Premium"


def test_returns_empty_list_without_active_students(client):
    api, _ = client
    trainer_headers = register_and_login(api, "empty-trainer@example.com", "TRAINER")

    response = api.get(STUDENTS_PATH, headers=trainer_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_returns_authorized_student_detail_and_metrics(client):
    api, sessions = client
    trainer_headers = register_and_login(api, "detail-trainer@example.com", "TRAINER")
    register_and_login(api, "detail-student@example.com", "STUDENT")
    relationship_id, student_id = create_relationship(
        sessions, "detail-trainer@example.com", "detail-student@example.com"
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        db.add(
            WorkoutSession(
                relationship_id=relationship_id,
                student_id=student_id,
                routine_id="routine-1",
                day_name="Día 1",
                modality="GYM",
                started_at=now,
                finished_at=now,
                rpe=8,
            )
        )
        db.commit()

    response = api.get(f"{STUDENTS_PATH}/{student_id}", headers=trainer_headers)

    assert response.status_code == 200
    detail = response.json()
    assert detail["profile"]["first_name"] == "Valeria"
    assert detail["relationship"]["package_title"] == "Plan Premium"
    assert detail["relationship"]["agreed_monthly_price"] == 12500
    assert detail["goals"]["fitness_goals"] == ["fuerza"]
    assert detail["limitations"]["protected_zones"] == ["Hombro derecho"]
    assert detail["metrics"]["finished_sessions"] == 1
    assert detail["metrics"]["last_rpe"] == 8
    assert detail["metrics"]["logged_sets"] == 0


def test_rejects_detail_for_another_trainer_or_terminated_relationship(client):
    api, sessions = client
    owner_headers = register_and_login(api, "owner@example.com", "TRAINER")
    other_headers = register_and_login(api, "other@example.com", "TRAINER")
    register_and_login(api, "protected-student@example.com", "STUDENT")
    _, student_id = create_relationship(sessions, "owner@example.com", "protected-student@example.com")

    other_response = api.get(f"{STUDENTS_PATH}/{student_id}", headers=other_headers)
    assert other_response.status_code == 404

    with sessions() as db:
        relationship = db.scalar(
            select(TrainingRelationship).where(TrainingRelationship.student_id == student_id)
        )
        relationship.status = "TERMINATED"
        db.commit()

    terminated_response = api.get(f"{STUDENTS_PATH}/{student_id}", headers=owner_headers)
    assert terminated_response.status_code == 404


def test_us20_assignments_include_contracted_plan_for_filtering(client):
    api, sessions = client
    trainer_headers = register_and_login(api, "plans-trainer@example.com", "TRAINER")
    register_and_login(api, "student-basic@example.com", "STUDENT")
    register_and_login(api, "student-premium@example.com", "STUDENT")
    register_and_login(api, "student-ended-plan@example.com", "STUDENT")
    create_relationship(sessions, "plans-trainer@example.com", "student-basic@example.com", plan_title="Plan Básico")
    create_relationship(sessions, "plans-trainer@example.com", "student-premium@example.com", plan_title="Plan Premium")
    create_relationship(
        sessions,
        "plans-trainer@example.com",
        "student-ended-plan@example.com",
        status="TERMINATED",
        plan_title="Plan Terminado",
    )

    response = api.get(ASSIGNMENTS_PATH, headers=trainer_headers)

    assert response.status_code == 200
    assignments = response.json()
    assert sorted(item["plan_title"] for item in assignments) == ["Plan Básico", "Plan Premium"]
    assert all(item["plan_id"] for item in assignments)
    assert len({item["plan_id"] for item in assignments}) == 2
