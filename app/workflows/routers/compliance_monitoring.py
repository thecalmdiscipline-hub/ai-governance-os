from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user, require_module_access
from app.models.user import User
from app.workflows.schemas.base import WorkflowRunRequest, WorkflowRunResponse
from app.workflows.services.runner import run_workflow

router = APIRouter(
    prefix="/compliance-monitoring",
    tags=["Workflows"],
    dependencies=[Depends(require_module_access("compliance_monitoring"))],
)

@router.get("/schema")
def schema():
    return WorkflowRunRequest.model_json_schema()

@router.post("/run", response_model=WorkflowRunResponse)
def run(
    body: WorkflowRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = run_workflow("compliance_monitoring", {"input": body.input, "context": body.context, "user": current_user.username}, user_id=current_user.id, org_id=current_user.organization_id)
    return result
