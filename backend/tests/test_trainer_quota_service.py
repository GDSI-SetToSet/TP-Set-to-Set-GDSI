from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from backend.src.models.student_profile import StudentProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.schemas.trainer import TrainerQuotaUpdate
from backend.src.services import trainer_service
from backend.src.services.trainer_service import (
    count_active_students,
    get_or_create_profile,
    quota_summary,
    update_quota,
)


def create_trainer(api, sessions) -> str:
    api.post("/api/v1/auth/register", json={"email": "coach@example.com", "password": "StrongPass123", "role": "TRAINER"})
    with sessions() as db:
        return db.scalar(select(User).where(User.email == "coach@example.com")).id


@pytest.mark.parametrize("value", [0, 100])
def test_quota_accepts_range_limits(value):
    assert TrainerQuotaUpdate(max_students=value).max_students == value


@pytest.mark.parametrize("value", [-1, 101])
def test_quota_outside_range_is_rejected(value):
    with pytest.raises(ValidationError) as caught:
        TrainerQuotaUpdate(max_students=value)
    assert caught.value.errors()[0]["msg"] == "Los cupos deben estar entre 0 y 100"


def test_missing_quota_defaults_to_zero():
    assert TrainerQuotaUpdate().max_students == 0
    assert TrainerQuotaUpdate(max_students=None).max_students == 0


def test_update_quota_recalculates_availability(client):
    api, sessions = client
    trainer_id = create_trainer(api, sessions)
    with sessions() as db:
        trainer = db.get(User, trainer_id)
        assert quota_summary(db, get_or_create_profile(db, trainer)) == {
            "max_students": 0,
            "active_students": 0,
            "available_slots": 0,
            "has_available_quota": False,
        }
        profile = update_quota(db, trainer, TrainerQuotaUpdate(max_students=20))
        assert quota_summary(db, profile)["available_slots"] == 20
        assert quota_summary(db, profile)["has_available_quota"] is True


def test_quota_is_exhausted_when_active_students_reach_limit(client, monkeypatch):
    api, sessions = client
    trainer_id = create_trainer(api, sessions)
    monkeypatch.setattr(trainer_service, "count_active_students", lambda db, profile: 5)
    with sessions() as db:
        trainer = db.get(User, trainer_id)
        profile = update_quota(db, trainer, TrainerQuotaUpdate(max_students=5))
        assert quota_summary(db, profile)["has_available_quota"] is False
        # Bajar el tope por debajo de los alumnos activos se permite; no quedan cupos negativos.
        profile = update_quota(db, trainer, TrainerQuotaUpdate(max_students=3))
        assert quota_summary(db, profile)["available_slots"] == 0
        assert trainer_service.has_available_quota(db, profile) is False


def test_count_active_students_queries_only_active_relationships(client):
    api, sessions = client
    trainer_id = create_trainer(api, sessions)
    api.post("/api/v1/auth/register", json={"email": "s1@example.com", "password": "StrongPass123", "role": "STUDENT"})
    api.post("/api/v1/auth/register", json={"email": "s2@example.com", "password": "StrongPass123", "role": "STUDENT"})

    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        trainer = db.get(User, trainer_id)
        trainer_profile = update_quota(db, trainer, TrainerQuotaUpdate(max_students=2))
        plan = TrainingPlan(
            trainer_id=trainer_profile.id,
            title="Plan Base",
            monthly_price=Decimal("25000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        s1_user = db.scalar(select(User).where(User.email == "s1@example.com"))
        s2_user = db.scalar(select(User).where(User.email == "s2@example.com"))
        s1_profile = StudentProfile(user_id=s1_user.id, status="PUBLISHED", created_at=now, updated_at=now)
        s2_profile = StudentProfile(user_id=s2_user.id, status="PUBLISHED", created_at=now, updated_at=now)
        db.add_all([plan, s1_profile, s2_profile])
        db.flush()

        db.add_all(
            [
                TrainingRelationship(
                    student_id=s1_profile.id,
                    trainer_id=trainer_profile.id,
                    plan_id=plan.id,
                    agreed_monthly_price=Decimal("25000.00"),
                    agreed_currency="ARS",
                    status="ACTIVE",
                    start_date=now.date(),
                ),
                TrainingRelationship(
                    student_id=s2_profile.id,
                    trainer_id=trainer_profile.id,
                    plan_id=plan.id,
                    agreed_monthly_price=Decimal("25000.00"),
                    agreed_currency="ARS",
                    status="TERMINATED",
                    start_date=now.date(),
                ),
            ]
        )
        db.commit()

        assert count_active_students(db, trainer_profile) == 1
        assert quota_summary(db, trainer_profile) == {
            "max_students": 2,
            "active_students": 1,
            "available_slots": 1,
            "has_available_quota": True,
        }
