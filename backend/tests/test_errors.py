import pytest
from backend.src.api.errors import PROBLEM_JSON_MEDIA_TYPE
from backend.src.core.constants import (
    INTERNAL_ERROR_MESSAGE,
    INVALID_CREDENTIALS_MESSAGE,
    VALIDATION_ERROR_MESSAGE,
)
from backend.src.main import create_app
from fastapi import HTTPException
from fastapi.testclient import TestClient

PROBLEM_FIELDS = {"type", "title", "status", "detail", "instance"}


def assert_problem(response, status_code, detail, path):
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith(PROBLEM_JSON_MEDIA_TYPE)
    body = response.json()
    assert PROBLEM_FIELDS <= body.keys()
    assert body["type"] == "about:blank"
    assert body["status"] == status_code
    assert body["detail"] == detail
    assert body["instance"] == path
    assert body["title"]
    return body


def test_invalid_credentials_use_problem_details(client):
    api, _ = client
    path = "/api/v1/auth/login"
    response = api.post(path, json={"email": "nadie@example.com", "password": "WrongPass123"})
    body = assert_problem(response, 401, INVALID_CREDENTIALS_MESSAGE, path)
    assert "errors" not in body


def test_duplicate_email_uses_problem_details(client, registered_user):
    api, _ = client
    path = "/api/v1/auth/register"
    response = api.post(path, json={"email": registered_user["email"], "password": "StrongPass123", "role": "STUDENT"})
    assert_problem(response, 409, "El correo electrónico ya se encuentra registrado.", path)


def test_lockout_keeps_retry_after_header(client, registered_user):
    api, _ = client
    path = "/api/v1/auth/login"
    for _ in range(5):
        response = api.post(path, json={"email": registered_user["email"], "password": "WrongPass123"})
    assert response.status_code == 423
    assert response.headers["content-type"].startswith(PROBLEM_JSON_MEDIA_TYPE)
    assert int(response.headers["retry-after"]) > 0


def test_missing_session_keeps_www_authenticate_header(client):
    api, _ = client
    path = "/api/v1/auth/me"
    response = api.get(path)
    assert_problem(response, 401, "No autenticado.", path)
    assert response.headers["www-authenticate"] == "Bearer"


def test_validation_errors_are_listed_per_field(client):
    api, _ = client
    path = "/api/v1/auth/register"
    response = api.post(path, json={"email": "nope", "password": "StrongPass123", "role": "ADMIN"})
    body = assert_problem(response, 422, VALIDATION_ERROR_MESSAGE, path)
    fields = {error["field"] for error in body["errors"]}
    assert fields == {"email", "role"}
    assert all(error["message"] for error in body["errors"])


def test_missing_body_is_reported(client):
    api, _ = client
    path = "/api/v1/auth/forgot-password"
    body = assert_problem(api.post(path), 422, VALIDATION_ERROR_MESSAGE, path)
    assert body["errors"][0]["field"] == "body"


def test_unknown_route_uses_problem_details(client):
    api, _ = client
    assert_problem(api.get("/no-existe"), 404, "Not Found", "/no-existe")


def test_unhandled_error_hides_internal_details():
    app = create_app(create_tables=False)

    @app.get("/boom")
    def boom():
        raise RuntimeError("detalle interno secreto")

    with TestClient(app, raise_server_exceptions=False) as api:
        response = api.get("/boom")
    assert_problem(response, 500, INTERNAL_ERROR_MESSAGE, "/boom")
    assert "secreto" not in response.text


@pytest.mark.parametrize("status_code", [400, 404])
def test_non_string_detail_falls_back_to_status_phrase(status_code):
    app = create_app(create_tables=False)

    @app.get("/raw")
    def raw():
        raise HTTPException(status_code=status_code, detail={"internal": "data"})

    with TestClient(app) as api:
        response = api.get("/raw")
    body = response.json()
    assert response.status_code == status_code
    assert body["detail"] == body["title"]
