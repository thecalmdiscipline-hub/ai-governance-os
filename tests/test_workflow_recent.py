from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import SECRET_KEY, ALGORITHM
from app.workflows.services.runner import run_workflow

client = TestClient(app)


def make_token() -> str:
    payload = {
        "sub": "dennis_admin",
        "role": "admin",
        "org_id": 1,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


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

    token = make_token()

    res = client.get(
        "/workflows/recent?limit=3",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1
