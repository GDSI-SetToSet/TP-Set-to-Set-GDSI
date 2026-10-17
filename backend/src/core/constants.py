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
SECONDS_PER_MINUTE: Final = 60

INVALID_CREDENTIALS_MESSAGE: Final = "Mail o contraseña incorrectos"
LOCKED_ACCOUNT_MESSAGE: Final = "Se excedió el límite de intentos. Volvé a intentar en {minutes} minutos."
PASSWORD_REQUIREMENTS_MESSAGE: Final = (
    "La contraseña debe tener entre 8 y 128 caracteres e incluir al menos una mayúscula, "
    "una minúscula y un número."
)
