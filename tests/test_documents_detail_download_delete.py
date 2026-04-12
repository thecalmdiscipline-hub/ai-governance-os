from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_document_detail_download_and_delete():
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
        files={"file": ("delete_me.txt", BytesIO(b"delete me content"), "text/plain")},
    )
    assert upload.status_code == 200
    doc = upload.json()["document"]
    document_id = doc["id"]

    detail = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["document"]["filename"] == "delete_me.txt"

    download = client.get(
        f"/documents/{document_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download.status_code == 200
    assert download.content == b"delete me content"

    delete = client.delete(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete.status_code == 200
    assert delete.json()["deleted"]["filename"] == "delete_me.txt"

    detail_after = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_after.status_code == 404
