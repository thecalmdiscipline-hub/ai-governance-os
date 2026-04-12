from fastapi.testclient import TestClient

from app.main import app
from app.workflows.services.runner import run_workflow

client = TestClient(app)


def test_workflow_recent_returns_items():
    run_workflow(
        "customer_support",
        {
            "input": {"issue": "recent test", "priority": "low"},
            "context": {},
            "user": "dennis_admin",
        },
        user_id=1,
        org_id=1,
    )

    login = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    res = client.get(
        "/workflows/recent?limit=3",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1
    assert len(data["items"]) <= 3
