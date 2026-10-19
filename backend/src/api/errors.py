"""Respuestas de error RFC 7807 (application/problem+json) para toda la API (Constitución, Reglas de Dominio Transversales)."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.src.core.constants import INTERNAL_ERROR_MESSAGE, VALIDATION_ERROR_MESSAGE

PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"
DEFAULT_PROBLEM_TYPE = "about:blank"
# Literal: el nombre de la constante cambió entre versiones de Starlette.
VALIDATION_ERROR_STATUS = 422

logger = logging.getLogger(__name__)


def problem_response(
    request: Request,
    status_code: int,
    detail: str,
    headers: dict[str, str] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": DEFAULT_PROBLEM_TYPE,
        "title": HTTPStatus(status_code).phrase,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
    }
    if errors is not None:
        content["errors"] = errors
    return JSONResponse(content, status_code=status_code, headers=headers, media_type=PROBLEM_JSON_MEDIA_TYPE)


def field_name(location: tuple[Any, ...]) -> str:
    parts = [str(part) for part in location if part not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        detail = exc.detail.get("detail", HTTPStatus(exc.status_code).phrase)
        errors = exc.detail.get("errors")
        return problem_response(request, exc.status_code, detail, headers=exc.headers, errors=errors)
    detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return problem_response(request, exc.status_code, detail, headers=exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"field": field_name(tuple(error["loc"])), "message": error["msg"]} for error in exc.errors()]
    return problem_response(request, VALIDATION_ERROR_STATUS, VALIDATION_ERROR_MESSAGE, errors=errors)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s %s", request.method, request.url.path, exc_info=exc)
    return problem_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, INTERNAL_ERROR_MESSAGE)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
