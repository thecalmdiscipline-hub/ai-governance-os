from __future__ import annotations

from typing import Any, Dict, Optional


def _is_email_like(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    v = v.strip()
    return ("@" in v) and ("." in v.split("@")[-1])


def sales_lead_qualification_run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = payload.get("input") or {}
    lead = inp.get("lead") or {}
    email = lead.get("email")
    company = lead.get("company")
    source = inp.get("source") or inp.get("channel") or payload.get("source")

    score = 0
    if company:
        score += 40
    if _is_email_like(email):
        score += 40
    if source:
        score += 20 if str(source).lower() in {"inbound", "website", "referral"} else 10

    if score >= 80:
        qualification = "high"
        next_actions = ["schedule_call", "send_pricing", "assign_sales_owner"]
    elif score >= 50:
        qualification = "medium"
        next_actions = ["request_missing_info", "send_intro_email"]
    else:
        qualification = "low"
        next_actions = ["nurture_sequence", "enrich_contact_data"]

    return {
        "workflow": "sales_lead_qualification",
        "status": "ok",
        "qualification": qualification,
        "score": score,
        "next_actions": next_actions,
        "received": payload,
        "user_id": user_id,
    }
