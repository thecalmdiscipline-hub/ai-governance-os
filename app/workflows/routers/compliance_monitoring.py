from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.workflows.schemas.base import WorkflowRunRequest, WorkflowRunResponse
from app.workflows.services.base import run_workflow

router = APIRouter(prefix="/workflows/compliance_monitoring", tags=["workflows"])

@router.post("/run", response_model=WorkflowRunResponse)
def run_compliance_monitoring(
    req: WorkflowRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # tenant isolation is enforced by get_current_user (org_id in token) and db lookup
    # later: persist runs + audit log
    result = run_workflow("compliance_monitoring", req.input, dry_run=req.dry_run)
    return result
