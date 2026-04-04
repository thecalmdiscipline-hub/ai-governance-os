from __future__ import annotations
from typing import Any, Dict, Optional
from uuid import uuid4

def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {})
    context = payload.get("context", {})
    user = payload.get("user")

    issue = input_data.get("issue") or input_data.get("ping") or "unknown_issue"
    priority = input_data.get("priority") or "normal"

    ticket_id = f"CS-{uuid4().hex[:10].upper()}"

    return {
        "ticket_id": ticket_id,
        "triage": {
            "issue": issue,
            "priority": priority,
            "suggested_action": "collect_more_details" if issue == "unknown_issue" else "investigate_and_respond",
        },
        "received": {
            "input": input_data,
            "context": context,
            "user": user,
        },
        "user_id": user_id,
    }
