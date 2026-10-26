"""Servicio de almacenamiento protegido para archivos de apto médico (US-43).

Los archivos se guardan en uploads/medical_clearances/<student_id>/ fuera
de la raíz pública de la aplicación web, y sólo se sirven mediante el endpoint
autenticado del backend.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

from fastapi import UploadFile

# Base configurable: relativa a la raíz del proceso (donde se lanza uvicorn)
UPLOADS_DIR = Path("backend/uploads/medical_clearances")

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
_UNSAFE_CHARS_RE = re.compile(
    r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069<>:\"|?*]"
)
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:+")
_WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


class StorageError(Exception):
    """Error de validación o I/O del servicio de almacenamiento."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def sanitize_filename(filename: str | None) -> str:
    """Normaliza un nombre de archivo eliminando componentes de ruta, prefijos de unidad y caracteres peligrosos."""
    raw = unicodedata.normalize("NFKC", filename or "apto").replace("\\", "/")
    basename = raw.split("/")[-1]
    basename = _WINDOWS_DRIVE_RE.sub("", basename)
    cleaned = _UNSAFE_CHARS_RE.sub("", basename).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        return "apto"

    stem = cleaned.split(".")[0].upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        ext = Path(cleaned).suffix
        cleaned = f"apto{ext}" if ext else "apto"

    if len(cleaned) > 200:
        ext = Path(cleaned).suffix[:15]
        cleaned = f"{cleaned[: 200 - len(ext)]}{ext}"
    return cleaned


async def save_upload(student_id: str, file: UploadFile) -> tuple[str, int]:
    """Valida y persiste el archivo en disco.

    Returns:
        Tupla (file_path_str, file_size_bytes).

    Raises:
        StorageError: si el MIME type no está permitido o el archivo supera 10 MB.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise StorageError(
            "Formato no soportado. Solo se aceptan archivos PDF, JPEG o PNG."
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise StorageError(
            "El archivo supera el tamaño máximo permitido de 10 MB."
        )
    if len(content) == 0:
        raise StorageError("El archivo está vacío.")

    safe_student_dir = sanitize_filename(student_id)
    base_dir = UPLOADS_DIR.resolve()
    dest_dir = (UPLOADS_DIR / safe_student_dir).resolve()
    if not dest_dir.is_relative_to(base_dir):
        raise StorageError("Ruta de almacenamiento inválida.")

    safe_name = f"{uuid.uuid4().hex}_{sanitize_filename(file.filename)}"
    dest_path = UPLOADS_DIR / safe_student_dir / safe_name
    if not dest_path.resolve().is_relative_to(base_dir):
        raise StorageError("Ruta de almacenamiento inválida.")

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content)
    except OSError as exc:
        raise StorageError("No se pudo almacenar el archivo en el servidor.") from exc

    return str(dest_path), len(content)


def open_upload(file_path: str) -> Path:
    """Devuelve el Path canónico verificando que el archivo existe dentro del directorio permitido.

    Raises:
        StorageError: si el archivo no se encuentra en disco, es un symlink o apunta fuera de UPLOADS_DIR.
    """
    if not file_path or "\x00" in file_path:
        raise StorageError("El archivo del certificado no se encontró en el servidor.")
    path = Path(file_path)
    if path.is_symlink():
        raise StorageError("El archivo del certificado no se encontró en el servidor.")
    resolved_base = UPLOADS_DIR.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(resolved_base) or not resolved_path.is_file():
        raise StorageError("El archivo del certificado no se encontró en el servidor.")
    return resolved_path
