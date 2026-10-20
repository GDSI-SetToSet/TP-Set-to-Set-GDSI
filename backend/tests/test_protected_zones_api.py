from fastapi import status

from backend.src.models import ProtectedZone
from backend.src.schemas.protected_zone import ProtectedZonesUpdate


URL = "/api/v1/students/me/protected-zones"


def register_and_login(test_client, email, role):
    test_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123", "role": role},
    )
    token = test_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_protected_zones_are_saved_and_returned(client, student_token_headers):
    test_client, session_factory = client

    response = test_client.put(
        URL,
        headers=student_token_headers,
        json={"zones": ["  Left knee ", "Lower back"]},
    )

    assert response.status_code == status.HTTP_200_OK
    assert [zone["body_area"] for zone in response.json()["zones"]] == ["Left knee", "Lower back"]
    with session_factory() as db:
        assert db.query(ProtectedZone).count() == 2


def test_removing_protected_zone_removes_its_restriction(client, student_token_headers):
    test_client, session_factory = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee", "Shoulder"]})

    response = test_client.put(URL, headers=student_token_headers, json={"zones": ["Shoulder"]})

    assert response.status_code == status.HTTP_200_OK
    assert [zone["body_area"] for zone in response.json()["zones"]] == ["Shoulder"]
    with session_factory() as db:
        assert [zone.body_area for zone in db.query(ProtectedZone).all()] == ["Shoulder"]


def test_empty_zone_list_clears_all_zones(client, student_token_headers):
    test_client, session_factory = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee"]})

    response = test_client.put(URL, headers=student_token_headers, json={"zones": []})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["zones"] == []
    with session_factory() as db:
        assert db.query(ProtectedZone).count() == 0


def test_protected_zones_are_private_to_the_owning_student(client, student_token_headers):
    test_client, _ = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee"]})
    other_student = register_and_login(test_client, "another-student@example.com", "STUDENT")
    trainer = register_and_login(test_client, "trainer@example.com", "TRAINER")

    assert test_client.get(URL, headers=other_student).json()["zones"] == []
    assert test_client.get(URL, headers=trainer).status_code == status.HTTP_403_FORBIDDEN
    assert test_client.put(URL, headers=trainer, json={"zones": []}).status_code == status.HTTP_403_FORBIDDEN


def test_invalid_zone_names_are_rejected_without_changing_saved_zones(client, student_token_headers):
    test_client, session_factory = client
    test_client.put(URL, headers=student_token_headers, json={"zones": ["Knee"]})

    for zones in ([" "], ["Knee", " knee "], ["x" * 81], ["zone"] * 21):
        response = test_client.put(URL, headers=student_token_headers, json={"zones": zones})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    with session_factory() as db:
        assert [zone.body_area for zone in db.query(ProtectedZone).all()] == ["Knee"]


def test_protected_zone_schema_normalizes_whitespace_and_rejects_case_insensitive_duplicates():
    assert ProtectedZonesUpdate(zones=["  Left knee  "]).zones == ["Left knee"]
