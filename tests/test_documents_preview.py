from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_document_preview_returns_text_for_txt_file():
    login = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    upload = client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("preview_test.txt", BytesIO(b"preview text content"), "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document"]["id"]

    preview = client.get(
        f"/documents/{document_id}/preview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert preview.status_code == 200
    data = preview.json()
    assert data["status"] == "ok"
    assert data["document"]["filename"] == "preview_test.txt"
    assert "preview text content" in data["preview"]["text"]
