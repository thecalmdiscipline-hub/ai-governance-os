from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.workflow_run import WorkflowRun


def get_workflow_dashboard_summary(db: Session, organization_id: int, limit: int = 5):
    total_runs = db.query(func.count(WorkflowRun.id)).filter(
        WorkflowRun.organization_id == organization_id
    ).scalar() or 0

    ok_runs = db.query(func.count(WorkflowRun.id)).filter(
        WorkflowRun.organization_id == organization_id,
        WorkflowRun.status == "ok",
    ).scalar() or 0

    error_runs = db.query(func.count(WorkflowRun.id)).filter(
        WorkflowRun.organization_id == organization_id,
        WorkflowRun.status == "error",
    ).scalar() or 0

    latest_rows = db.query(WorkflowRun).filter(
        WorkflowRun.organization_id == organization_id
    ).order_by(WorkflowRun.id.desc()).limit(limit).all()

    latest_runs = []
    for row in latest_rows:
        latest_runs.append({
            "id": row.id,
            "run_id": row.run_id,
            "workflow": row.workflow,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        })

    grouped = db.query(
        WorkflowRun.workflow,
        func.count(WorkflowRun.id).label("count")
    ).filter(
        WorkflowRun.organization_id == organization_id
    ).group_by(
        WorkflowRun.workflow
    ).order_by(
        func.count(WorkflowRun.id).desc(),
        WorkflowRun.workflow.asc()
    ).all()

    workflow_cards = []
    for workflow, count in grouped:
        workflow_cards.append({
            "workflow": workflow,
            "count": int(count),
        })

    success_rate = 0.0
    if total_runs > 0:
        success_rate = round((ok_runs / total_runs) * 100, 2)

    return {
        "stats": {
            "total_runs": int(total_runs),
            "ok_runs": int(ok_runs),
            "error_runs": int(error_runs),
            "success_rate": success_rate,
        },
        "latest_runs": latest_runs,
        "workflow_cards": workflow_cards,
    }
