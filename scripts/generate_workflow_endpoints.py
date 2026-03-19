from pathlib import Path

WORKFLOWS = [
    ("customer_support", "customer-support"),
    ("document_knowledge", "document-knowledge"),
    ("sales_lead_qualification", "sales-lead-qualification"),
    ("quote_contract_generator", "quote-contract-generator"),
    ("meeting_agenda_assistant", "meeting-agenda-assistant"),
    ("marketing_automation", "marketing-automation"),
    ("invoice_processing", "invoice-processing"),
    ("compliance_monitoring", "compliance-monitoring"),
    ("hr_recruitment", "hr-recruitment"),
    ("business_intelligence", "business-intelligence"),
]

TEMPLATE = """from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.workflows.schemas.base import WorkflowRunRequest, WorkflowRunResponse
from app.workflows.services.base import run_workflow_stub

router = APIRouter(prefix="/workflows/{prefix}", tags=["Workflows"])

@router.get("/schema")
def schema():
    return WorkflowRunRequest.model_json_schema()

@router.post("/run", response_model=WorkflowRunResponse)
def run(
    body: WorkflowRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = run_workflow_stub("{name}", {{"input": body.input, "context": body.context, "user": current_user.username}})
    return result
"""

out_dir = Path("app/workflows/routers")
out_dir.mkdir(parents=True, exist_ok=True)

for name, prefix in WORKFLOWS:
    (out_dir / f"{name}.py").write_text(TEMPLATE.format(name=name, prefix=prefix), encoding="utf-8")
