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


def list_workflow_runs(
    db: Session,
    organization_id: int,
    workflow: Optional[str] = None,
    limit: int = 50,
):
    q = db.query(WorkflowRun).filter(
        WorkflowRun.organization_id == organization_id
    )

    if workflow:
        q = q.filter(WorkflowRun.workflow == workflow)

    rows = q.order_by(WorkflowRun.id.desc()).limit(limit).all()

    items = []
    for row in rows:
        items.append({
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
        })

    return {
        "total": len(items),
        "items": items,
    }
