from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import SECRET_KEY, ALGORITHM

client = TestClient(app)


def make_token():
    payload = {
        "sub": "dennis_admin",
        "role": "admin",
        "org_id": 1,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def test_workflow_dashboard_returns_frontend_payload():
    token = make_token()

    # Org 1 (dennis_admin) does not have customer_support_ai activated in
    # test.db — that's intentional ambient state, asserted as the negative
    # case in test_modules_endpoint.py. document-knowledge is a module org 1
    # does have (document_intelligence), so it exercises a real run without
    # mutating shared tenant-module state that other tests depend on.
    run_res = client.post(
        "/workflows/document-knowledge/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "input": {"question": "dashboard test"},
            "context": {},
        },
    )
    assert run_res.status_code == 200

    res = client.get(
        "/workflows/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()

    assert "stats" in data
    assert "workflow_cards" in data
    assert "recent_runs" in data
    assert "history" in data

    assert "total_runs" in data["stats"]
    assert isinstance(data["workflow_cards"], list)
    assert isinstance(data["recent_runs"], list)
    assert isinstance(data["history"], list)
