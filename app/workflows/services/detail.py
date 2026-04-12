import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.workflow_run import WorkflowRun


def _loads(value: Optional[str]):
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def get_workflow_run_detail(
    db: Session,
    organization_id: int,
    run_id: str,
):
    row = db.query(WorkflowRun).filter(
        WorkflowRun.organization_id == organization_id,
        WorkflowRun.run_id == run_id,
    ).first()

    if row is None:
        return None

    return {
        "id": row.id,
        "run_id": row.run_id,
        "workflow": row.workflow,
        "status": row.status,
        "organization_id": row.organization_id,
        "user_id": row.user_id,
        "input_payload": _loads(row.input_payload),
        "context_payload": _loads(row.context_payload),
        "output_payload": _loads(row.output_payload),
        "error": row.error,
        "message": row.message,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
