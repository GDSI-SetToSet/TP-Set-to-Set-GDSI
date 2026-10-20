from fastapi import status


def test_save_own_profile_success(client, student_token_headers):
    test_client, _ = client
    
    payload = {
        "first_name": "Delfina",
        "last_name": "Videla",
        "fitness_goals": ["fuerza", "salud_general"],
        "birth_date": "2000-01-01T00:00:00Z",
        "contact_phone": "+541123456789"
    }
    response = test_client.put(
        "/api/v1/students/me/profile",
        headers=student_token_headers,
        json=payload
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "PUBLISHED"
    assert data["first_name"] == "Delfina"
    assert data["last_name"] == "Videla"
    assert data["status"] == "PUBLISHED"

def test_save_own_profile_invalid_phone(client, student_token_headers):
    test_client, _ = client
    
    payload = {
        "first_name": "Delfina",
        "last_name": "Videla",
        "fitness_goals": ["fuerza", "salud_general"],
        "birth_date": "2000-01-01T00:00:00Z",
        "contact_phone": "123" # Inválido
    }
    response = test_client.put(
        "/api/v1/students/me/profile",
        headers=student_token_headers,
        json=payload
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_save_own_profile_draft_mode(client, student_token_headers):
    test_client, _ = client
    
    payload = {
        "first_name": "Delfina"
    }
    response = test_client.put(
        "/api/v1/students/me/profile",
        headers=student_token_headers,
        json=payload
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "DRAFT"

def test_get_own_profile(client, student_token_headers):
    test_client, _ = client
    
    response = test_client.get(
        "/api/v1/students/me/profile",
        headers=student_token_headers
    )
    assert response.status_code == status.HTTP_200_OK
    assert "status" in response.json()


def profile_payload(**overrides):
    return {
        "first_name": "Delfina",
        "last_name": "Videla",
        "birth_date": "2000-01-01T00:00:00Z",
        "contact_phone": "+541123456789",
        "fitness_goals": ["fuerza"],
        **overrides,
    }


def put_profile(test_client, headers, **overrides):
    return test_client.put("/api/v1/students/me/profile", headers=headers, json=profile_payload(**overrides))


def test_missing_last_name_stays_draft(client, student_token_headers):
    test_client, _ = client
    response = put_profile(test_client, student_token_headers, last_name=None)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "DRAFT"


def test_phone_with_spaces_or_too_long_is_rejected(client, student_token_headers):
    test_client, _ = client
    for phone in ("+54 9 11 4444-5555", "1" * 16):
        response = put_profile(test_client, student_token_headers, contact_phone=phone)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_no_goals_stays_draft(client, student_token_headers):
    test_client, _ = client
    response = put_profile(test_client, student_token_headers, fitness_goals=[])
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "DRAFT"


def test_invalid_duplicate_or_null_goals_rejected(client, student_token_headers):
    test_client, _ = client
    for goals in (["yoga"], ["fuerza", "fuerza"], None):
        response = put_profile(test_client, student_token_headers, fitness_goals=goals)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_goals_update_is_reflected_immediately(client, student_token_headers):
    test_client, _ = client
    put_profile(test_client, student_token_headers)
    put_profile(test_client, student_token_headers, fitness_goals=["resistencia", "movilidad_rehabilitacion"])
    data = test_client.get("/api/v1/students/me/profile", headers=student_token_headers).json()
    assert data["fitness_goals"] == ["resistencia", "movilidad_rehabilitacion"]


def test_motivation_is_optional_for_publishing(client, student_token_headers):
    test_client, _ = client
    response = put_profile(test_client, student_token_headers)
    assert response.json()["status"] == "PUBLISHED"
    assert response.json()["personal_motivation"] is None


def test_published_profile_cannot_drop_all_goals(client, student_token_headers):
    test_client, _ = client
    put_profile(test_client, student_token_headers)
    response = put_profile(test_client, student_token_headers, fitness_goals=[])
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()["errors"][0]["field"] == "fitness_goals"


def register_and_login(test_client, email, role):
    test_client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123", "role": role})
    token = test_client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_goals_visibility(client, student_token_headers):
    test_client, _ = client
    own = put_profile(test_client, student_token_headers, personal_motivation="Volver a correr").json()
    url = f"/api/v1/students/{own['id']}/goals"

    response = test_client.get(url, headers=student_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"fitness_goals": ["fuerza"], "personal_motivation": "Volver a correr"}

    trainer = register_and_login(test_client, "entrenador@example.com", "TRAINER")
    assert test_client.get(url, headers=trainer).status_code == status.HTTP_403_FORBIDDEN

    other = register_and_login(test_client, "otra@example.com", "STUDENT")
    assert test_client.get(url, headers=other).status_code == status.HTTP_403_FORBIDDEN

    missing = "/api/v1/students/does-not-exist/goals"
    assert test_client.get(missing, headers=student_token_headers).status_code == status.HTTP_404_NOT_FOUND
