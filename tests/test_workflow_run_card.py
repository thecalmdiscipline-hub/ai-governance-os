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


def test_workflow_run_card_contains_input_output():
    token = make_token()

    run_res = client.post(
        "/workflows/customer-support/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "input": {"issue": "card test", "priority": "high"},
            "context": {},
        },
    )

    assert run_res.status_code == 200
    run_id = run_res.json()["run_id"]

    res = client.get(
        f"/workflows/runs/{run_id}/card",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200

    data = res.json()

    assert "run" in data
    assert "input" in data
    assert "output" in data

    assert data["run"]["run_id"] == run_id
    assert isinstance(data["input"], dict)
    assert isinstance(data["output"], dict)
