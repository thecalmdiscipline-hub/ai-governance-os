from typing import Any, Dict, Optional
from uuid import uuid4

from app.workflows.registry import WORKFLOWS, normalize_workflow_key


def run_workflow(workflow_key: str, payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    run_id = str(uuid4())
    key = normalize_workflow_key(workflow_key)

    fn = WORKFLOWS.get(key)
    if not fn:
        return {
            "workflow": key,
            "run_id": run_id,
            "status": "error",
            "output": {},
            "error": "unknown_workflow",
            "message": f"Workflow not registered: {key}",
        }

    try:
        result = fn(payload=payload, user_id=user_id)
        return {
            "workflow": key,
            "run_id": run_id,
            "status": "ok",
            "output": result if isinstance(result, dict) else {"result": result},
            "error": None,
            "message": None,
        }
    except Exception as e:
        return {
            "workflow": key,
            "run_id": run_id,
            "status": "error",
            "output": {},
            "error": "exception",
            "message": str(e),
        }
