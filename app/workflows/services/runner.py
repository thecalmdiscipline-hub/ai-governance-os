from typing import Dict, Any, Optional
from uuid import uuid4

from app.workflows.registry import WORKFLOWS

def _normalize_key(key: str) -> str:
    return key.replace("-", "_").strip().lower()

def run_workflow(workflow_key: str, payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    run_id = str(uuid4())
    key = _normalize_key(workflow_key)
    fn = WORKFLOWS.get(key)
    if not fn:
        return {
            "run_id": run_id,
            "status": "error",
            "error": "unknown_workflow",
            "workflow": key,
        }
    try:
        result = fn(payload=payload, user_id=user_id)
        return {
            "run_id": run_id,
            "status": "ok",
            "workflow": key,
            "result": result,
        }
    except Exception as e:
        return {
            "run_id": run_id,
            "status": "error",
            "error": "exception",
            "message": str(e),
            "workflow": key,
        }
