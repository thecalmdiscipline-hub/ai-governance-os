from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_workflow_detail_not_found():
    login = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    res = client.get(
        "/workflows/runs/does-not-exist",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 404
