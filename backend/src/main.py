from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.api.errors import register_exception_handlers
from backend.src.api.v1.auth import router as auth_router
from backend.src.api.v1.discovery import router as discovery_router
from backend.src.api.v1.students import router as students_router
from backend.src.api.v1.trainers import router as trainers_router
from backend.src.core.config import API_TITLE, API_VERSION, CORS_ALLOWED_ORIGINS
from backend.src.core.database import Base, engine
from backend.src.models import (  # noqa: F401
    MedicalClearance,
    PasswordResetToken,
    StudentProfile,
    TrainerProfile,
    TrainingPlan,
    TrainingRequest,
    User,
    UserSession,
)


def create_app(create_tables: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if create_tables:
            Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(CORS_ALLOWED_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Retry-After"],
    )
    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(trainers_router)
    app.include_router(students_router)
    app.include_router(discovery_router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
