from typing import Any, Dict, Optional
from datetime import datetime

def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    lead = payload.get("lead", {}) if isinstance(payload.get("lead"), dict) else {}
    email = lead.get("email")
    company = lead.get("company")
    source = payload.get("source")

    score = 0
    reasons = []

    if email:
        score += 20
        reasons.append("email_present")
    if company:
        score += 20
        reasons.append("company_present")
    if source in ("inbound", "referral"):
        score += 30
        reasons.append("high_intent_source")

    tier = "cold"
    if score >= 60:
        tier = "hot"
    elif score >= 40:
        tier = "warm"

    return {
        "workflow": "sales-lead-qualification",
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "result": {
            "score": score,
            "tier": tier,
            "reasons": reasons,
        },
    }
