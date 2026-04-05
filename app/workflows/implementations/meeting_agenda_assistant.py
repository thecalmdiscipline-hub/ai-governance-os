from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = (payload or {}).get("input") or {}
    context = (payload or {}).get("context") or {}
    user = (payload or {}).get("user")

    title = inp.get("title") or inp.get("meeting_title") or "Meeting"
    participants = inp.get("participants") or []
    duration_min = inp.get("duration_minutes") or inp.get("duration_min") or 30
    topics = inp.get("topics") or []
    goals = inp.get("goals") or []
    decisions_needed = inp.get("decisions_needed") or []

    agenda_items = []
    if topics:
        per_topic = max(5, int(duration_min / max(1, len(topics))))
        for t in topics:
            agenda_items.append({"topic": t, "minutes": per_topic})
    else:
        agenda_items = [
            {"topic": "Check-in & objectives", "minutes": 5},
            {"topic": "Main discussion", "minutes": max(10, int(duration_min) - 15)},
            {"topic": "Decisions & next steps", "minutes": 10},
        ]

    return {
        "agenda_id": f"MA-{uuid4().hex[:10].upper()}",
        "status": "ok",
        "meeting": {
            "title": title,
            "duration_minutes": int(duration_min),
            "participants": participants,
        },
        "agenda": agenda_items,
        "notes": {
            "goals": goals,
            "decisions_needed": decisions_needed,
        },
        "meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "received": {"input": inp, "context": context, "user": user},
            "user_id": user_id,
        },
    }
