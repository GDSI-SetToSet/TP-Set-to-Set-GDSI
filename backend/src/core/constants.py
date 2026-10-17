from typing import Final

TRAINER_ROLE: Final = "TRAINER"
STUDENT_ROLE: Final = "STUDENT"
VALID_USER_ROLES: Final[frozenset[str]] = frozenset({TRAINER_ROLE, STUDENT_ROLE})

PASSWORD_MIN_LENGTH: Final = 8
PASSWORD_MAX_LENGTH: Final = 128
PASSWORD_UPPERCASE_PATTERN: Final = r"[A-Z]"
PASSWORD_LOWERCASE_PATTERN: Final = r"[a-z]"
PASSWORD_NUMBER_PATTERN: Final = r"[0-9]"

SECONDS_PER_DAY: Final = 24 * 60 * 60

INVALID_CREDENTIALS_MESSAGE: Final = "Mail o contraseña incorrectos"
LOCKED_ACCOUNT_MESSAGE: Final = "La cuenta está bloqueada temporalmente. Intentá de nuevo en {minutes} minutos."
PASSWORD_TOO_SHORT_MESSAGE: Final = "La contraseña debe tener al menos 8 caracteres."
PASSWORD_MISSING_UPPERCASE_MESSAGE: Final = "La contraseña debe incluir al menos una mayúscula."
PASSWORD_MISSING_LOWERCASE_MESSAGE: Final = "La contraseña debe incluir al menos una minúscula."
PASSWORD_MISSING_NUMBER_MESSAGE: Final = "La contraseña debe incluir al menos un número."
