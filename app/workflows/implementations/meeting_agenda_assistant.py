from __future__ import annotations

from uuid import uuid4
from typing import Any, Dict, List


def meeting_agenda_assistant(payload: Dict[str, Any], user_id: int | None = None) -> Dict[str, Any]:
    input_data = (payload or {}).get("input") or {}
    context = (payload or {}).get("context") or {}

    title = input_data.get("title") or "Meeting"
    duration_min = int(input_data.get("duration_min") or 30)
    participants = input_data.get("participants") or []
    goals = input_data.get("goals") or []

    agenda: List[Dict[str, Any]] = []
    remaining = max(duration_min, 10)

    agenda.append({"topic": "Opening", "minutes": 3})
    remaining -= 3

    if goals:
        agenda.append({"topic": "Goals & desired outcomes", "minutes": min(7, remaining)})
        remaining -= agenda[-1]["minutes"]

    if participants:
        agenda.append({"topic": "Roundtable updates", "minutes": min(10, remaining)})
        remaining -= agenda[-1]["minutes"]

    if remaining > 0:
        agenda.append({"topic": "Main discussion", "minutes": max(remaining - 5, 5)})
        remaining -= agenda[-1]["minutes"]

    agenda.append({"topic": "Decisions & next steps", "minutes": max(remaining, 2)})

    action_items = []
    if goals:
        action_items.append({"owner": "tbd", "action": "Summarize outcomes vs goals"})
    action_items.append({"owner": "tbd", "action": "Send notes and follow-ups"})

    return {
        "meeting_id": f"MA-{uuid4().hex[:10].upper()}",
        "status": "ok",
        "title": title,
        "duration_min": duration_min,
        "agenda": agenda,
        "action_items": action_items,
        "received": {"input": input_data, "context": context, "user": (payload or {}).get("user")},
        "user_id": user_id,
    }
