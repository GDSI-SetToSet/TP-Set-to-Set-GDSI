from decimal import Decimal

import pytest
from backend.src.models.user import User
from backend.src.schemas.trainer import TrainingPlanCreate, TrainingPlanUpdate
from backend.src.services.trainer_service import (
    TrainerProfileError,
    archive_plan,
    create_plan,
    list_own_plans,
    update_plan,
)
from pydantic import ValidationError
from sqlalchemy import select


def create_trainer(api, sessions, email: str = "coach@example.com") -> str:
    api.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": "TRAINER"})
    with sessions() as db:
        return db.scalar(select(User).where(User.email == email)).id


def error_messages(error: ValidationError) -> dict[str, str]:
    return {str(item["loc"][0]): item["msg"] for item in error.errors()}


def test_plan_defaults_to_ars_and_is_active(client):
    api, sessions = client
    trainer_id = create_trainer(api, sessions)
    with sessions() as db:
        trainer = db.get(User, trainer_id)
        plan = create_plan(db, trainer, TrainingPlanCreate(title="Plan Fuerza", monthly_price=Decimal(28000)))
        assert plan.currency == "ARS"
        assert plan.is_active is True
        assert plan.monthly_price == Decimal("28000.00")


@pytest.mark.parametrize("price", ["0", "1000000"])
def test_price_accepts_range_limits(price):
    assert TrainingPlanCreate(title="Plan", monthly_price=Decimal(price)).monthly_price == Decimal(price)


@pytest.mark.parametrize("price", ["-0.01", "1000000.01"])
def test_price_outside_range_is_rejected(price):
    with pytest.raises(ValidationError) as caught:
        TrainingPlanCreate(title="Plan", monthly_price=Decimal(price))
    assert error_messages(caught.value)["monthly_price"] == "La tarifa debe estar entre $0 y $1.000.000"


def test_missing_title_and_price_are_required():
    with pytest.raises(ValidationError) as caught:
        TrainingPlanCreate(title="   ")
    assert error_messages(caught.value) == {
        "title": "Este campo es obligatorio",
        "monthly_price": "Este campo es obligatorio",
    }


def test_update_cannot_clear_required_fields():
    with pytest.raises(ValidationError) as caught:
        TrainingPlanUpdate(title=None, monthly_price=None)
    assert set(error_messages(caught.value)) == {"title", "monthly_price"}


def test_currency_must_be_three_letter_code():
    assert TrainingPlanCreate(title="Plan", monthly_price=Decimal(10), currency="usd").currency == "USD"
    with pytest.raises(ValidationError):
        TrainingPlanCreate(title="Plan", monthly_price=Decimal(10), currency="PESOS")


def test_edit_and_archive_keep_plan_history(client):
    api, sessions = client
    trainer_id = create_trainer(api, sessions)
    with sessions() as db:
        trainer = db.get(User, trainer_id)
        plan = create_plan(db, trainer, TrainingPlanCreate(title="Plan Fuerza", monthly_price=Decimal(28000)))
        edited = update_plan(db, trainer, plan.id, TrainingPlanUpdate(monthly_price=Decimal(30000)))
        assert edited.monthly_price == Decimal("30000.00")
        assert edited.title == "Plan Fuerza"
        archived = archive_plan(db, trainer, plan.id)
        assert archived.is_active is False
        # El paquete archivado se conserva: los vínculos activos guardan su propio arancel (no retroactividad).
        assert [stored.id for stored in list_own_plans(db, trainer)] == [plan.id]


def test_trainer_cannot_modify_plans_of_another_trainer(client):
    api, sessions = client
    owner_id = create_trainer(api, sessions)
    other_id = create_trainer(api, sessions, "other@example.com")
    with sessions() as db:
        plan = create_plan(db, db.get(User, owner_id), TrainingPlanCreate(title="Plan", monthly_price=Decimal(10)))
        other = db.get(User, other_id)
        with pytest.raises(TrainerProfileError) as caught:
            update_plan(db, other, plan.id, TrainingPlanUpdate(title="Robado"))
        assert caught.value.status_code == 404
        with pytest.raises(TrainerProfileError):
            archive_plan(db, other, plan.id)
