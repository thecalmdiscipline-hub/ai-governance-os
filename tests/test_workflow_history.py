from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import SECRET_KEY, ALGORITHM
from app.db.session import SessionLocal
from app.models.user import User
from app.workflows.services.runner import run_workflow

client = TestClient(app)


def make_token() -> str:
    payload = {
        "sub": "dennis_admin",
        "role": "admin",
        "org_id": 1,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


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

    token = make_token()

    res = client.get(
        "/workflows/history?limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1
