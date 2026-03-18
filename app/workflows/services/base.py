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
