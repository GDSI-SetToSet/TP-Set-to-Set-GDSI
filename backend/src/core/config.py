import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_TITLE = "Set to Set API"
API_VERSION = "0.1.0"
API_V1_PREFIX = "/api/v1"
CORS_ALLOWED_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./set_to_set.db")
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    if APP_ENV == "production":
        raise RuntimeError("JWT_SECRET debe configurarse en el entorno de producción.")
    JWT_SECRET = "local-development-secret-change-before-deploying"
if APP_ENV == "production" and len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres en producción.")
JWT_ALGORITHM = "HS256"
SESSION_DAYS = 30
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
