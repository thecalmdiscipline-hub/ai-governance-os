from app.main import app
from app.db.session import SessionLocal
from app.workflows.services.runner import run_workflow
from app.models.workflow_run import WorkflowRun


def test_workflow_run_is_persisted():
    db = SessionLocal()
    before = db.query(WorkflowRun).count()
    db.close()

    result = run_workflow(
        "customer_support",
        {"input": {"issue": "printer broken"}, "context": {}, "user": "test_user"},
        user_id=1,
        org_id=1,
    )

    assert result["status"] == "ok"
    assert result["workflow"] == "customer_support"

    db = SessionLocal()
    after = db.query(WorkflowRun).count()
    row = db.query(WorkflowRun).order_by(WorkflowRun.id.desc()).first()
    db.close()

    assert after == before + 1
    assert row is not None
    assert row.workflow == "customer_support"
    assert row.status == "ok"
    assert row.organization_id == 1
    assert row.user_id == 1
