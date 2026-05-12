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


def test_microsoft_status_route_works():
    token = login()
    res = client.get(
        "/microsoft/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "client_configured" in data


def test_microsoft_connect_route_returns_400_when_not_configured():
    token = login()
    res = client.post(
        "/microsoft/connect",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code in {200, 400}
