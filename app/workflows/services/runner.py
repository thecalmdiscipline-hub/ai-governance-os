from typing import Any, Dict, Optional
from app.workflows.registry import WORKFLOWS
from app.workflows.services.base import run_workflow_stub

def run_workflow(workflow_key: str, payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    if workflow_key not in WORKFLOWS:
        return {"status": "error", "error": "unknown_workflow", "workflow": workflow_key}
    return run_workflow_stub(workflow_key, payload, user_id=user_id)
