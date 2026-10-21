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

PASSWORD_RESET_TOKEN_MINUTES = 60
PASSWORD_RESET_URL = os.getenv("PASSWORD_RESET_URL", "http://localhost:5173/restablecer-contrasena")

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "console").strip().lower()
if EMAIL_BACKEND not in ("console", "smtp"):
    raise RuntimeError("EMAIL_BACKEND debe ser 'console' o 'smtp'.")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Set to Set <no-reply@settoset.local>")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"
if EMAIL_BACKEND == "smtp" and not SMTP_HOST:
    raise RuntimeError("SMTP_HOST debe configurarse cuando EMAIL_BACKEND es 'smtp'.")
