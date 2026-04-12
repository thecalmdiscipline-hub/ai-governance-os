from sqlalchemy.orm import Session

from app.workflows.services.detail import get_workflow_run_detail


def get_frontend_run_card(db: Session, organization_id: int, run_id: str):
    item = get_workflow_run_detail(
        db=db,
        organization_id=organization_id,
        run_id=run_id,
    )

    if item is None:
        return None

    return {
        "run": {
            "id": item["id"],
            "run_id": item["run_id"],
            "workflow": item["workflow"],
            "status": item["status"],
            "created_at": item["created_at"],
        },
        "input": item["input_payload"],
        "output": item["output_payload"],
        "error": item["error"],
        "message": item["message"],
    }
