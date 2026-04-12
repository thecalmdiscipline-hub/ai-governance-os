from sqlalchemy.orm import Session

from app.workflows.services.dashboard import get_workflow_dashboard_summary
from app.workflows.services.history import list_workflow_runs


def get_frontend_dashboard_payload(db: Session, organization_id: int):
    summary = get_workflow_dashboard_summary(
        db=db,
        organization_id=organization_id,
        limit=5,
    )

    history = list_workflow_runs(
        db=db,
        organization_id=organization_id,
        workflow=None,
        limit=10,
    )

    return {
        "stats": summary["stats"],
        "workflow_cards": summary["workflow_cards"],
        "recent_runs": summary["latest_runs"],
        "history": history["items"],
    }
