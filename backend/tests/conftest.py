import pytest
from backend.src.core.database import Base, get_db
from backend.src.main import create_app
from backend.src.models import (  # noqa: F401
    MedicalClearance,
    Notification,
    PasswordResetToken,
    TrainerProfile,
    TrainingPlan,
    TrainingRelationship,
    TrainingRequest,
    User,
    UserSession,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)
    app = create_app(create_tables=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def registered_user(client):
    test_client, _ = client
    response = test_client.post(
        "/api/v1/auth/register",
        json={"email": "alumna@example.com", "password": "StrongPass123", "role": "STUDENT"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def student_token_headers(client, registered_user):
    test_client, _ = client

    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "alumna@example.com", "password": "StrongPass123"}
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}
