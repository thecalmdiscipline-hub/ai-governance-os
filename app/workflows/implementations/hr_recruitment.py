from __future__ import annotations
from typing import Any, Dict, Optional

def hr_recruitment(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = (payload or {}).get("input", {})
    candidates = inp.get("candidates", [])

    scored = [{"name": c.get("name"), "score": 50} for c in candidates if isinstance(c, dict)]

    return {
        "status": "ok",
        "candidates": scored,
        "received": payload,
        "user_id": user_id,
    }
