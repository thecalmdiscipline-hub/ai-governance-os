#!/usr/bin/env bash
set -euo pipefail

# Run from repo root
if [ ! -d "app" ]; then
  echo "ERROR: run this from repo root (where ./app exists)"
  exit 1
fi

echo "==> Creating folders"
mkdir -p app/workflows/definitions
mkdir -p app/workflows/runtime
mkdir -p app/api
mkdir -p tests
mkdir -p .github/workflows

echo "==> Writing workflow types"
cat > app/workflows/runtime/types.py << 'PY'
from pydantic import BaseModel
from typing import Any, Dict, Optional, Literal

WorkflowStatus = Literal["queued", "running", "succeeded", "failed"]

class WorkflowRunRequest(BaseModel):
    # Generic payload. Each workflow validates internally if needed.
    payload: Dict[str, Any] = {}

class WorkflowRunResult(BaseModel):
    status: WorkflowStatus
    output: Dict[str, Any] = {}
    error: Optional[str] = None

class WorkflowDefinition(BaseModel):
    workflow_id: str
    name: str
    description: str
    required_role: str  # "admin" | "auditor" | "operator"
PY

echo "==> Writing workflow registry (10 workflows)"
cat > app/workflows/registry.py << 'PY'
from typing import Callable, Dict
from app.workflows.runtime.types import WorkflowDefinition, WorkflowRunRequest, WorkflowRunResult

Runner = Callable[[WorkflowRunRequest], WorkflowRunResult]

def _stub_ok(workflow_id: str) -> Runner:
    def run(req: WorkflowRunRequest) -> WorkflowRunResult:
        # Stub runner: returns deterministic output so tests can pass.
        return WorkflowRunResult(
            status="succeeded",
            output={
                "workflow_id": workflow_id,
                "received_keys": sorted(list(req.payload.keys())),
                "message": "stub runner executed"
            }
        )
    return run

WORKFLOWS: Dict[str, Dict] = {
    "support_agent": {
        "def": WorkflowDefinition(
            workflow_id="support_agent",
            name="AI Klantenservice Agent",
            description="Beantwoordt klantvragen, triage tickets, escaleert complexe cases.",
            required_role="operator",
        ),
        "runner": _stub_ok("support_agent"),
    },
    "knowledge_agent": {
        "def": WorkflowDefinition(
            workflow_id="knowledge_agent",
            name="Document / Knowledge AI",
            description="Doorzoekt documenten, Q&A, samenvattingen (RAG).",
            required_role="operator",
        ),
        "runner": _stub_ok("knowledge_agent"),
    },
    "sales_lead_agent": {
        "def": WorkflowDefinition(
            workflow_id="sales_lead_agent",
            name="Sales Lead Kwalificatie Agent",
            description="Lead scoring, opvolging, meeting scheduling.",
            required_role="operator",
        ),
        "runner": _stub_ok("sales_lead_agent"),
    },
    "quote_contract_generator": {
        "def": WorkflowDefinition(
            workflow_id="quote_contract_generator",
            name="Offerte en Contract Generator",
            description="Genereert offertes/contracten met templates.",
            required_role="admin",
        ),
        "runner": _stub_ok("quote_contract_generator"),
    },
    "meeting_assistant": {
        "def": WorkflowDefinition(
            workflow_id="meeting_assistant",
            name="Meeting & Agenda AI Assistant",
            description="Planning, notes, actiepunten, samenvattingen.",
            required_role="operator",
        ),
        "runner": _stub_ok("meeting_assistant"),
    },
    "marketing_automation": {
        "def": WorkflowDefinition(
            workflow_id="marketing_automation",
            name="Marketing Automation Agent",
            description="Campagnes, content, follow-ups.",
            required_role="operator",
        ),
        "runner": _stub_ok("marketing_automation"),
    },
    "invoice_processing": {
        "def": WorkflowDefinition(
            workflow_id="invoice_processing",
            name="Factuurverwerking Automation",
            description="Extract, classify, route, bookkeep-ready output.",
            required_role="admin",
        ),
        "runner": _stub_ok("invoice_processing"),
    },
    "compliance_monitoring": {
        "def": WorkflowDefinition(
            workflow_id="compliance_monitoring",
            name="Compliance Monitoring AI",
            description="Doorlopende checks op policies/risks/evidence.",
            required_role="auditor",
        ),
        "runner": _stub_ok("compliance_monitoring"),
    },
    "hr_recruitment": {
        "def": WorkflowDefinition(
            workflow_id="hr_recruitment",
            name="HR Recruitment Automation",
            description="CV screening, shortlist, scheduling.",
            required_role="admin",
        ),
        "runner": _stub_ok("hr_recruitment"),
    },
    "business_intelligence": {
        "def": WorkflowDefinition(
            workflow_id="business_intelligence",
            name="Business Intelligence Agent",
            description="KPI’s, dashboards, insights (stub).",
            required_role="admin",
        ),
        "runner": _stub_ok("business_intelligence"),
    },
}

def list_workflows():
    return [v["def"] for v in WORKFLOWS.values()]

def get_workflow(workflow_id: str):
    return WORKFLOWS.get(workflow_id)
PY

echo "==> Writing workflows router"
cat > app/api/workflows.py << 'PY'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.workflows.registry import list_workflows, get_workflow
from app.workflows.runtime.types import WorkflowRunRequest
from app.core.audit import create_audit_log
from app.api.dependencies import get_db, get_current_user

router = APIRouter(tags=["workflows"])

@router.get("/workflows")
def workflows_index(current_user=Depends(get_current_user)):
    return {"workflows": [w.dict() for w in list_workflows()]}

def _role_rank(role: str) -> int:
    order = {"operator": 1, "auditor": 2, "admin": 3}
    return order.get(role, 0)

@router.post("/workflows/{workflow_id}/run")
def run_workflow(
    workflow_id: str,
    req: WorkflowRunRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_workflow(workflow_id)
    if not item:
        raise HTTPException(status_code=404, detail="Workflow not found")

    wf_def = item["def"]
    # Minimal RBAC: require at least the required_role
    if _role_rank(current_user.role) < _role_rank(wf_def.required_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    runner = item["runner"]
    result = runner(req)

    create_audit_log(
        db=db,
        organization_id=int(current_user.organization_id),
        entity_type="workflow",
        entity_id=0,
        action="run",
        details=f"Workflow {workflow_id} executed. status={result.status}",
        performed_by=current_user.username
    )

    return {"workflow_id": workflow_id, "result": result.dict()}
PY

echo "==> Writing tests (basic contract tests)"
cat > tests/test_workflows.py << 'PY'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_workflows_requires_auth():
    # If your get_current_user expects Bearer token, this should be 401
    r = client.get("/workflows")
    assert r.status_code in (401, 403)

def test_workflow_not_found_requires_auth_first():
    r = client.post("/workflows/does_not_exist/run", json={"payload": {}})
    assert r.status_code in (401, 403)
PY

echo "==> Writing GitHub Actions CI"
cat > .github/workflows/ci.yml << 'YML'
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.9"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx ruff

      - name: Lint
        run: ruff check .

      - name: Tests
        run: pytest -q
YML

echo "==> Done. Next: register router in app/main.py"
echo "Add this line in app/main.py after other include_router calls:"
echo "    app.include_router(workflows.router)"
echo ""
echo "And add import:"
echo "    from app.api import workflows"
PY