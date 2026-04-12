from io import BytesIO
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_document_upload_and_list():
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
        files={"file": ("test_document.txt", BytesIO(b"hello upload"), "text/plain")},
    )

    assert upload.status_code == 200
    upload_data = upload.json()
    assert upload_data["status"] == "ok"
    assert upload_data["document"]["filename"] == "test_document.txt"

    listing = client.get(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert listing.status_code == 200
    listing_data = listing.json()
    assert listing_data["status"] == "ok"
    assert listing_data["total"] >= 1
    assert any(item["filename"] == "test_document.txt" for item in listing_data["items"])
