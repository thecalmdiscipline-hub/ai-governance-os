#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# folders
mkdir -p app/workflows
mkdir -p app/workflows/routers
mkdir -p app/workflows/schemas
mkdir -p app/workflows/services
mkdir -p tests/workflows

# init files
touch app/workflows/__init__.py
touch app/workflows/routers/__init__.py
touch app/workflows/schemas/__init__.py
touch app/workflows/services/__init__.py
touch tests/workflows/__init__.py

# list of workflows (10)
workflows=(
  "customer_support"
  "document_knowledge"
  "sales_lead_qualification"
  "quote_contract_generator"
  "meeting_agenda_assistant"
  "marketing_automation"
  "invoice_processing"
  "compliance_monitoring"
  "hr_recruitment"
  "business_intelligence"
)

# shared minimal base schema (request/response)
cat > app/workflows/schemas/base.py <<'PY'
from pydantic import BaseModel
from typing import Optional, Dict, Any

class WorkflowRunRequest(BaseModel):
    # later: input payload per workflow (now generic)
    input: Dict[str, Any]
    dry_run: bool = True
    correlation_id: Optional[str] = None

class WorkflowRunResponse(BaseModel):
    workflow: str
    status: str
    dry_run: bool
    output: Dict[str, Any]
PY

# shared minimal service
cat > app/workflows/services/base.py <<'PY'
from typing import Dict, Any

def run_workflow(workflow_name: str, payload: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    # placeholder: later hook into agent orchestration / tools
    return {
        "workflow": workflow_name,
        "status": "ok",
        "dry_run": dry_run,
        "output": {
            "message": f"{workflow_name} executed (stub).",
            "received_keys": sorted(list(payload.keys()))
        }
    }
PY

# create routers + tests
for wf in "${workflows[@]}"; do
  # router
  cat > "app/workflows/routers/${wf}.py" <<PY
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.user import User
from app.workflows.schemas.base import WorkflowRunRequest, WorkflowRunResponse
from app.workflows.services.base import run_workflow

router = APIRouter(prefix="/workflows/${wf}", tags=["workflows"])

@router.post("/run", response_model=WorkflowRunResponse)
def run_${wf}(
    req: WorkflowRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # tenant isolation is enforced by get_current_user (org_id in token) and db lookup
    # later: persist runs + audit log
    result = run_workflow("${wf}", req.input, dry_run=req.dry_run)
    return result
PY

  # test
  cat > "tests/workflows/test_${wf}.py" <<PY
def test_${wf}_router_exists():
    # smoke test: importing router should work
    from app.workflows.routers.${wf} import router  # noqa: F401
PY
done

# aggregator: import all routers in one place
cat > app/workflows/routers/all.py <<'PY'
from app.workflows.routers.customer_support import router as customer_support
from app.workflows.routers.document_knowledge import router as document_knowledge
from app.workflows.routers.sales_lead_qualification import router as sales_lead_qualification
from app.workflows.routers.quote_contract_generator import router as quote_contract_generator
from app.workflows.routers.meeting_agenda_assistant import router as meeting_agenda_assistant
from app.workflows.routers.marketing_automation import router as marketing_automation
from app.workflows.routers.invoice_processing import router as invoice_processing
from app.workflows.routers.compliance_monitoring import router as compliance_monitoring
from app.workflows.routers.hr_recruitment import router as hr_recruitment
from app.workflows.routers.business_intelligence import router as business_intelligence

ALL_WORKFLOW_ROUTERS = [
    customer_support,
    document_knowledge,
    sales_lead_qualification,
    quote_contract_generator,
    meeting_agenda_assistant,
    marketing_automation,
    invoice_processing,
    compliance_monitoring,
    hr_recruitment,
    business_intelligence,
]
PY

echo "OK: workflow layer scaffold created."
