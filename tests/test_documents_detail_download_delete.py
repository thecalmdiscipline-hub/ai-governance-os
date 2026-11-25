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
        files={"file": ("[scope=kennis] delete_me.txt", BytesIO(b"scope: kennis\ndelete me content"), "text/plain")},
    )
    assert upload.status_code == 200
    doc = upload.json()["document"]
    document_id = doc["id"]

    detail = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["document"]["filename"] == "[scope=kennis] delete_me.txt"

    download = client.get(
        f"/documents/{document_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download.status_code == 200
    assert download.content == b"scope: kennis\ndelete me content"

    delete = client.delete(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete.status_code == 200
    assert delete.json()["deleted"]["filename"] == "[scope=kennis] delete_me.txt"

    detail_after = client.get(
        f"/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_after.status_code == 404
