from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import SECRET_KEY, ALGORITHM
from app.core.audit import create_audit_log
from app.db.session import SessionLocal

client = TestClient(app)


def make_token():
    payload = {
        "sub": "dennis_admin",
        "role": "admin",
        "org_id": 1,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def test_audit_endpoint_filters_entity_type_and_action():
    db = SessionLocal()

    create_audit_log(
        db=db,
        organization_id=1,
        entity_type="document",
        entity_id=111,
        action="uploaded",
        details="document uploaded test",
        performed_by="dennis_admin",
    )

    create_audit_log(
        db=db,
        organization_id=1,
        entity_type="workflow_run",
        entity_id=222,
        action="deleted",
        details="workflow deleted test",
        performed_by="dennis_admin",
    )

    token = make_token()

    res = client.get(
        "/audit?entity_type=workflow_run&action=deleted&limit=20",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["total"] >= 1
    assert any(
        item["entity_type"] == "workflow_run" and item["action"] == "deleted"
        for item in data["items"]
    )

    db.close()
