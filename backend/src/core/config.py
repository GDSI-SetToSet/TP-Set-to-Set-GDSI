import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

API_TITLE = "Set to Set API"
API_VERSION = "0.1.0"
API_V1_PREFIX = "/api/v1"

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
CORS_ALLOWED_ORIGINS = tuple(
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173" if APP_ENV != "production" else "",
    ).split(",")
    if origin.strip()
)
if APP_ENV == "production" and not CORS_ALLOWED_ORIGINS:
    raise RuntimeError("CORS_ALLOWED_ORIGINS debe incluir el dominio del frontend en producción.")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./set_to_set.db").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

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

# Configuración de IA para generación de rutinas particulares (US-13)
DEFAULT_AI_PROVIDER = "heuristic"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_GEMINI_TIMEOUT_SECONDS = 30.0

AI_PROVIDER = (os.getenv("AI_PROVIDER") or os.getenv("AI_ROUTINE_PROVIDER") or DEFAULT_AI_PROVIDER).strip().lower()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip() or None
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS") or DEFAULT_GEMINI_TIMEOUT_SECONDS)


def get_ai_provider() -> str:
    return (os.getenv("AI_PROVIDER") or os.getenv("AI_ROUTINE_PROVIDER") or DEFAULT_AI_PROVIDER).strip().lower()


def get_gemini_api_key() -> str | None:
    return (os.getenv("GEMINI_API_KEY") or "").strip() or None


def get_gemini_model() -> str:
    return (os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()


def get_gemini_timeout_seconds() -> float:
    raw = (os.getenv("GEMINI_TIMEOUT_SECONDS") or "").strip()
    if not raw:
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
    try:
        val = float(raw)
        return val if val > 0 else DEFAULT_GEMINI_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
