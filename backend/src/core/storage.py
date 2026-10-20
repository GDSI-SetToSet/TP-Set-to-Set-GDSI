"""Servicio de almacenamiento protegido para archivos de apto médico (US-43).

Los archivos se guardan en uploads/medical_clearances/<student_id>/ fuera
de la raíz pública de la aplicación web, y sólo se sirven mediante el endpoint
autenticado del backend.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

# Base configurable: relativa a la raíz del proceso (donde se lanza uvicorn)
UPLOADS_DIR = Path("backend/uploads/medical_clearances")

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB


class StorageError(Exception):
    """Error de validación o I/O del servicio de almacenamiento."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


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

    dest_dir = UPLOADS_DIR / student_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'apto').name}"
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(content)

    return str(dest_path), len(content)


def open_upload(file_path: str) -> Path:
    """Devuelve el Path verificando que el archivo existe.

    Raises:
        StorageError: si el archivo no se encuentra en disco.
    """
    path = Path(file_path)
    if not path.exists():
        raise StorageError("El archivo del certificado no se encontró en el servidor.")
    return path
