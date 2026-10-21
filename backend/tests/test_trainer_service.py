import pytest
from sqlalchemy import select

from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.user import User
from backend.src.schemas.trainer import TrainerProfileUpdate
from backend.src.services.trainer_service import (
    TrainerProfileError,
    get_or_create_profile,
    update_profile,
)


def create_trainer(api, sessions):
    api.post("/api/v1/auth/register", json={"email": "coach@example.com", "password": "StrongPass123", "role": "TRAINER"})
    with sessions() as db:
        return db.scalar(select(User).where(User.email == "coach@example.com")).id


def test_draft_profile_accepts_partial_updates_and_publishes_when_complete(client):
    api, sessions = client
    trainer_id = create_trainer(api, sessions)
    with sessions() as db:
        trainer = db.get(User, trainer_id)
        profile = get_or_create_profile(db, trainer)
        assert profile.status == "DRAFT"
        profile = update_profile(db, trainer, TrainerProfileUpdate(bio="Entrenador de fuerza"))
        assert profile.bio == "Entrenador de fuerza"
        assert profile.status == "DRAFT"
        profile = update_profile(
            db,
            trainer,
            TrainerProfileUpdate(full_name="Lucas Pérez", contact_phone="+5491155551234", specialty="Fuerza"),
        )
        assert profile.status == "PUBLISHED"


def test_published_profile_cannot_remove_required_fields(client):
    api, sessions = client
    trainer_id = create_trainer(api, sessions)
    with sessions() as db:
        trainer = db.get(User, trainer_id)
        update_profile(
            db,
            trainer,
            TrainerProfileUpdate(full_name="Lucas Pérez", contact_phone="+5491155551234", specialty="Fuerza"),
        )
        with pytest.raises(TrainerProfileError):
            update_profile(db, trainer, TrainerProfileUpdate(contact_phone=None))
        stored = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == trainer_id))
        assert stored.contact_phone == "+5491155551234"
        assert stored.status == "PUBLISHED"


@pytest.mark.parametrize("phone", ["123", "123-456-789", "+1234567890123456"])
def test_phone_format_is_validated(phone):
    with pytest.raises(ValueError):
        TrainerProfileUpdate(contact_phone=phone)

