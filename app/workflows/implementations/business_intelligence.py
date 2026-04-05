from __future__ import annotations
from typing import Any, Dict, Optional

def business_intelligence(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = (payload or {}).get("input", {})
    metrics = inp.get("metrics", {})

    return {
        "status": "ok",
        "insights": {k: v for k,v in metrics.items()},
        "received": payload,
        "user_id": user_id,
    }
