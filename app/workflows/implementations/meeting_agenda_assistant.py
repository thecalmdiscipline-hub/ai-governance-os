from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

def meeting_agenda_assistant(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = (payload or {}).get("input") or {}
    title = inp.get("title") or "Meeting"
    duration_min = int(inp.get("duration_min") or 30)
    participants = inp.get("participants") or []
    goals = inp.get("goals") or []

    if not isinstance(participants, list):
        participants = [str(participants)]
    if not isinstance(goals, list):
        goals = [str(goals)]

    blocks: List[Dict[str, Any]] = []
    if goals:
        per = max(5, duration_min // max(1, len(goals)))
        t = 0
        for g in goals:
            blocks.append({"start_min": t, "duration_min": per, "topic": str(g)})
            t += per
        if t < duration_min:
            blocks.append({"start_min": t, "duration_min": duration_min - t, "topic": "Wrap-up / Actions"})
    else:
        blocks = [
            {"start_min": 0, "duration_min": max(5, duration_min - 5), "topic": "Discussion"},
            {"start_min": max(0, duration_min - 5), "duration_min": 5, "topic": "Wrap-up / Actions"},
        ]

    return {
        "status": "ok",
        "agenda_id": f"MA-{uuid4().hex[:10].upper()}",
        "title": title,
        "duration_min": duration_min,
        "participants": participants,
        "agenda": blocks,
        "received": payload,
        "user_id": user_id,
    }
