from __future__ import annotations
from typing import Any, Dict, Optional

def compliance_monitoring(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "status": "ok",
        "issues_found": 0,
        "risk_level": "low",
        "received": payload,
        "user_id": user_id,
    }
