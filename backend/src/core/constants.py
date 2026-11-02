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
VALIDATION_ERROR_MESSAGE: Final = "Los datos enviados no son válidos."
INTERNAL_ERROR_MESSAGE: Final = "Ocurrió un error inesperado. Intentá de nuevo más tarde."
LOCKED_ACCOUNT_MESSAGE: Final = "Se excedió el límite de intentos. Volvé a intentar en {minutes} minutos."
PASSWORD_REQUIREMENTS_MESSAGE: Final = (
    "La contraseña debe tener entre 8 y 128 caracteres e incluir al menos una mayúscula, "
    "una minúscula y un número."
)

PASSWORD_RESET_REQUESTED_MESSAGE: Final = "Si el correo está registrado, recibirás un enlace de recuperación."
PASSWORD_RESET_SUCCESS_MESSAGE: Final = "Tu contraseña se actualizó. Iniciá sesión con tu nueva contraseña."
INVALID_RESET_TOKEN_MESSAGE: Final = "El enlace de recuperación no es válido o expiró. Solicitá uno nuevo."
PASSWORD_RESET_EMAIL_SUBJECT: Final = "Restablecé tu contraseña de Set to Set"
# Zonas corporales válidas (las mismas que ofrece el alumno al declarar sus zonas a proteger).
BODY_AREAS: Final = (
    "Neck",
    "Shoulder",
    "Elbow",
    "Wrist and hand",
    "Upper back",
    "Lower back",
    "Hip",
    "Knee",
    "Ankle and foot",
)

BODY_AREAS_ES: Final = {
    "neck": "cuello",
    "shoulder": "hombro",
    "elbow": "codo",
    "wrist and hand": "muñeca y mano",
    "upper back": "espalda alta",
    "lower back": "espalda baja",
    "hip": "cadera",
    "knee": "rodilla",
    "ankle and foot": "tobillo y pie",
}
ZONE_SYNONYMS: Final[dict[str, str]] = {
    "cuello": "neck",
    "neck": "neck",
    "cervical": "neck",
    "trapecio": "neck",
    "hombro": "shoulder",
    "shoulder": "shoulder",
    "hombros": "shoulder",
    "deltoides": "shoulder",
    "deltoid": "shoulder",
    "manguito": "shoulder",
    "codo": "elbow",
    "elbow": "elbow",
    "codos": "elbow",
    "muñeca y mano": "wrist and hand",
    "wrist and hand": "wrist and hand",
    "muñeca": "wrist and hand",
    "muneca": "wrist and hand",
    "mano": "wrist and hand",
    "wrist": "wrist and hand",
    "hand": "wrist and hand",
    "espalda alta": "upper back",
    "upper back": "upper back",
    "dorsal": "upper back",
    "romboides": "upper back",
    "espalda baja": "lower back",
    "lower back": "lower back",
    "lumbar": "lower back",
    "lumbares": "lower back",
    "raquis": "lower back",
    "cadera": "hip",
    "hip": "hip",
    "caderas": "hip",
    "pelvis": "hip",
    "gluteo": "hip",
    "glúteo": "hip",
    "gluteos": "hip",
    "glúteos": "hip",
    "rodilla": "knee",
    "knee": "knee",
    "rodillas": "knee",
    "patela": "knee",
    "rotula": "knee",
    "rótula": "knee",
    "tobillo y pie": "ankle and foot",
    "ankle and foot": "ankle and foot",
    "tobillo": "ankle and foot",
    "tobillos": "ankle and foot",
    "pie": "ankle and foot",
    "pies": "ankle and foot",
    "ankle": "ankle and foot",
    "foot": "ankle and foot",
}


def canonical_zone_key(area: str | None) -> str:
    if not area:
        return ""
    clean = area.strip().lower()
    if clean in ZONE_SYNONYMS:
        return ZONE_SYNONYMS[clean]
    for term, canon in ZONE_SYNONYMS.items():
        if term in clean:
            return canon
    return clean


PASSWORD_RESET_EMAIL_BODY: Final = (
    "Recibimos un pedido para restablecer tu contraseña.\n\n"
    "Para definir una nueva, abrí este enlace dentro de los próximos {minutes} minutos:\n"
    "{link}\n\n"
    "Si no lo pediste, ignorá este correo: tu contraseña no va a cambiar."
)
