from fastapi.testclient import TestClient

from app.main import app
from app.workflows.services.runner import run_workflow

client = TestClient(app)


def test_workflow_detail_returns_single_run():
    result = run_workflow(
        "customer_support",
        {
            "input": {"issue": "detail test", "priority": "high"},
            "context": {},
            "user": "dennis_admin",
        },
        user_id=1,
        org_id=1,
    )

    run_id = result["run_id"]

    login = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    res = client.get(
        f"/workflows/runs/{run_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["run_id"] == run_id
    assert data["workflow"] == "customer_support"
    assert data["status"] == "ok"
