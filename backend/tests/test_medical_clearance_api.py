import io

from fastapi import status

from backend.src.core.storage import sanitize_filename
from backend.src.models import MedicalClearance

URL_ME = "/api/v1/students/me/medical-clearance"


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


def test_student_can_upload_valid_pdf_clearance(client, student_token_headers):
    test_client, session_factory = client
    pdf_content = b"%PDF-1.4 test file content"
    files = {"file": ("apto.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {"issue_date": "2026-10-01"}

    response = test_client.post(URL_ME, headers=student_token_headers, files=files, data=data)

    assert response.status_code == status.HTTP_201_CREATED
    payload = response.json()
    assert payload["status"] == "CURRENT"
    assert payload["original_filename"] == "apto.pdf"
    assert payload["mime_type"] == "application/pdf"
    assert payload["file_size_bytes"] == len(pdf_content)
    assert payload["issue_date"] == "2026-10-01"

    with session_factory() as db:
        record = db.query(MedicalClearance).filter_by(id=payload["id"]).one()
        assert record.status == "CURRENT"
        assert record.original_filename == "apto.pdf"


def test_student_can_upload_images(client, student_token_headers):
    test_client, _ = client
    # JPEG
    jpeg_content = b"\xff\xd8\xff test image"
    files = {"file": ("apto.jpg", io.BytesIO(jpeg_content), "image/jpeg")}
    response = test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-09-15"})
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["mime_type"] == "image/jpeg"

    # PNG
    png_content = b"\x89PNG test image"
    files = {"file": ("apto.png", io.BytesIO(png_content), "image/png")}
    response = test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-09-20"})
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["mime_type"] == "image/png"


def test_unsupported_file_format_is_rejected(client, student_token_headers):
    test_client, _ = client
    files = {"file": ("doc.docx", io.BytesIO(b"word document"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-10-01"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Formato no soportado" in response.text or "format" in response.text.lower()


def test_file_exceeding_max_size_is_rejected(client, student_token_headers):
    test_client, _ = client
    # 10 MB + 1 byte
    too_large = b"a" * (10 * 1024 * 1024 + 1)
    files = {"file": ("large.pdf", io.BytesIO(too_large), "application/pdf")}
    response = test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-10-01"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "10 MB" in response.text or "tamaño" in response.text.lower()


def test_empty_file_is_rejected(client, student_token_headers):
    test_client, _ = client
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    response = test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-10-01"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_new_upload_archives_previous_version(client, student_token_headers):
    test_client, session_factory = client
    # First upload
    f1 = {"file": ("first.pdf", io.BytesIO(b"content1"), "application/pdf")}
    r1 = test_client.post(URL_ME, headers=student_token_headers, files=f1, data={"issue_date": "2026-08-01"})
    assert r1.status_code == status.HTTP_201_CREATED
    first_id = r1.json()["id"]

    # Second upload
    f2 = {"file": ("second.pdf", io.BytesIO(b"content2"), "application/pdf")}
    r2 = test_client.post(URL_ME, headers=student_token_headers, files=f2, data={"issue_date": "2026-10-01"})
    assert r2.status_code == status.HTTP_201_CREATED
    second_id = r2.json()["id"]

    with session_factory() as db:
        old_rec = db.query(MedicalClearance).filter_by(id=first_id).one()
        new_rec = db.query(MedicalClearance).filter_by(id=second_id).one()
        assert old_rec.status == "ARCHIVED"
        assert new_rec.status == "CURRENT"


def test_get_own_medical_clearance_metadata(client, student_token_headers):
    test_client, _ = client
    # Before upload -> 404
    assert test_client.get(URL_ME, headers=student_token_headers).status_code == status.HTTP_404_NOT_FOUND

    # After upload -> 200
    files = {"file": ("apto.pdf", io.BytesIO(b"content"), "application/pdf")}
    test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-10-01"})

    response = test_client.get(URL_ME, headers=student_token_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "CURRENT"
    assert response.json()["original_filename"] == "apto.pdf"


def test_student_can_download_own_certificate(client, student_token_headers):
    test_client, _ = client
    profile_id = test_client.get("/api/v1/students/me/profile", headers=student_token_headers).json()["id"]
    download_url = f"/api/v1/students/{profile_id}/medical-clearance/download"

    # Before upload -> 404
    assert test_client.get(download_url, headers=student_token_headers).status_code == status.HTTP_404_NOT_FOUND

    pdf_bytes = b"%PDF-1.4 sample content for download"
    files = {"file": ("my_cert.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-10-01"})

    download_resp = test_client.get(download_url, headers=student_token_headers)
    assert download_resp.status_code == status.HTTP_200_OK
    assert download_resp.content == pdf_bytes
    assert "application/pdf" in download_resp.headers["content-type"]


def test_unauthorized_trainer_cannot_download_student_clearance(client, student_token_headers):
    test_client, _ = client
    profile_id = test_client.get("/api/v1/students/me/profile", headers=student_token_headers).json()["id"]
    download_url = f"/api/v1/students/{profile_id}/medical-clearance/download"

    files = {"file": ("secret.pdf", io.BytesIO(b"confidential"), "application/pdf")}
    test_client.post(URL_ME, headers=student_token_headers, files=files, data={"issue_date": "2026-10-01"})

    # Trainer without access -> 403 Forbidden
    trainer_headers = register_and_login(test_client, "trainer-unauth@example.com", "TRAINER")
    resp = test_client.get(download_url, headers=trainer_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Another student -> 403 Forbidden
    other_student_headers = register_and_login(test_client, "other-student@example.com", "STUDENT")
    resp_other = test_client.get(download_url, headers=other_student_headers)
    assert resp_other.status_code == status.HTTP_403_FORBIDDEN


def test_download_without_token_is_unauthorized(client, student_token_headers):
    test_client, _ = client
    profile_id = test_client.get("/api/v1/students/me/profile", headers=student_token_headers).json()["id"]
    download_url = f"/api/v1/students/{profile_id}/medical-clearance/download"

    assert test_client.get(download_url).status_code == status.HTTP_401_UNAUTHORIZED


def test_trainer_cannot_upload_medical_clearance(client):
    test_client, _ = client
    trainer_headers = register_and_login(test_client, "trainer-uploader@example.com", "TRAINER")
    files = {"file": ("apto.pdf", io.BytesIO(b"pdf data"), "application/pdf")}
    response = test_client.post(URL_ME, headers=trainer_headers, files=files, data={"issue_date": "2026-10-01"})
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_filename_path_traversal_is_sanitized_and_open_upload_rejects_outside_paths(
    client, student_token_headers
):
    assert sanitize_filename("..\\..\\../etc/malicious\r\nname.pdf") == "maliciousname.pdf"
    assert sanitize_filename("..") == "apto"
    assert sanitize_filename(None) == "apto"

    test_client, session_factory = client
    profile_id = test_client.get("/api/v1/students/me/profile", headers=student_token_headers).json()["id"]
    download_url = f"/api/v1/students/{profile_id}/medical-clearance/download"

    pdf_bytes = b"%PDF-1.4 sanitized upload"
    files = {"file": ("..\\..\\../etc/secret_apto.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    upload_resp = test_client.post(
        URL_ME,
        headers=student_token_headers,
        files=files,
        data={"issue_date": "2026-10-01"},
    )
    assert upload_resp.status_code == status.HTTP_201_CREATED
    body = upload_resp.json()
    assert body["original_filename"] == "secret_apto.pdf"

    # Tamper stored file_path to point outside UPLOADS_DIR -> download must fail with 404
    with session_factory() as db:
        rec = db.query(MedicalClearance).filter_by(id=body["id"]).one()
        rec.file_path = "README.md"
        db.commit()

    tampered_resp = test_client.get(download_url, headers=student_token_headers)
    assert tampered_resp.status_code == status.HTTP_404_NOT_FOUND
