from typing import Any, Dict, Optional
from datetime import datetime

def run_workflow_stub(workflow_key: str, payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "workflow": workflow_key,
        "user_id": user_id,
        "received": payload,
        "status": "stub",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
