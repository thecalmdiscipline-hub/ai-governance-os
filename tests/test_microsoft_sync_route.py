from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def login() -> str:
    res = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_microsoft_sync_requires_existing_connection_or_token():
    token = login()
    res = client.post(
        "/microsoft/sync",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "No Microsoft connection found"
