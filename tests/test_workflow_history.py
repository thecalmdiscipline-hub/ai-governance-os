from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.workflows.services.runner import run_workflow

client = TestClient(app)


def test_workflow_history_returns_items():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "dennis_admin").first()
    db.close()

    assert user is not None
    assert user.organization_id == 1

    run_workflow(
        "customer_support",
        {
            "input": {"issue": "history test", "priority": "medium"},
            "context": {},
            "user": "dennis_admin",
        },
        user_id=user.id,
        org_id=user.organization_id,
    )

    login = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    res = client.get(
        "/workflows/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 1
    assert any(item["workflow"] == "customer_support" for item in data["items"])
