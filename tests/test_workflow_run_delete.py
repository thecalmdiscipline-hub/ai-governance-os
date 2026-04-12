from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.security import SECRET_KEY, ALGORITHM
from app.workflows.services.runner import run_workflow
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.workflow_run import WorkflowRun

client = TestClient(app)


def make_token() -> str:
    payload = {
        "sub": "dennis_admin",
        "role": "admin",
        "org_id": 1,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def test_workflow_run_delete_removes_run_and_creates_audit_log():
    result = run_workflow(
        "customer_support",
        {
            "input": {"issue": "delete test", "priority": "high"},
            "context": {},
            "user": "dennis_admin",
        },
        user_id=1,
        org_id=1,
    )

    run_id = result["run_id"]
    token = make_token()

    delete_res = client.delete(
        f"/workflows/runs/{run_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["status"] == "ok"

    db = SessionLocal()

    row = db.query(WorkflowRun).filter(WorkflowRun.run_id == run_id).first()
    assert row is None

    log = (
        db.query(AuditLog)
        .filter(
            AuditLog.organization_id == 1,
            AuditLog.entity_type == "workflow_run",
            AuditLog.action == "deleted",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )

    db.close()

    assert log is not None
    assert run_id in (log.details or "")
