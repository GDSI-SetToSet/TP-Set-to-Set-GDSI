from fastapi import status

def test_save_own_profile_success(client, student_token_headers):
    test_client, _ = client
    
    payload = {
        "full_name": "Delfina Videla",
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
    assert data["full_name"] == "Delfina Videla"

def test_save_own_profile_invalid_phone(client, student_token_headers):
    test_client, _ = client
    
    payload = {
        "full_name": "Delfina Videla",
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
        "full_name": "Delfina Videla"
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