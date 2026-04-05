from __future__ import annotations
from typing import Any, Dict, Optional

def marketing_automation(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = (payload or {}).get("input", {})
    campaign = inp.get("campaign") or "default_campaign"
    audience = inp.get("audience") or "broad"

    return {
        "status": "ok",
        "campaign": campaign,
        "audience": audience,
        "actions": ["email_sequence", "retargeting_ads"],
        "received": payload,
        "user_id": user_id,
    }
