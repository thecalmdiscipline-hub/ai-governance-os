"""
Meeting Agenda Assistant workflow — LLM implementation.

Input fields (all optional):
  title              : Meeting title
  duration_min       : Total meeting duration in minutes (default 30)
  participants       : List of participant names or roles
  goals              : Meeting goals or topics to cover
  context            : Background context or pre-read material
  meeting_type       : Type of meeting (kickoff, review, planning, retrospective, etc.)

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  agenda_id          : Unique agenda ID (MA-xxxx)
  title              : Meeting title
  duration_min       : Total duration
  participants       : Participant list (echoed)
  agenda             : list[{start_min, duration_min, topic, desired_outcome, facilitator_notes}]
  preparation_tips   : list[{participant, tips}]
  decision_points    : list[str] — key decisions to make in this meeting
  action_items_template : list[str] — action item placeholders to capture
  meeting_summary    : str — brief narrative on meeting purpose and expected outcome
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an enterprise meeting facilitator AI. Generate professional, results-oriented agendas for business meetings.

Analyse the meeting brief and return a structured JSON agenda.
Return valid JSON only — no prose, no markdown.

Required JSON schema:
{
  "agenda": [
    {
      "topic": "<agenda item title>",
      "duration_min": <integer minutes for this item>,
      "desired_outcome": "<what should be decided, aligned, or produced by end of this block>",
      "facilitator_notes": "<tip for the facilitator running this block>"
    }
  ],
  "preparation_tips": [
    {
      "participant": "<participant name or role>",
      "tips": ["<specific preparation tip 1>", "<tip 2>"]
    }
  ],
  "decision_points": ["<key decision that must be made in this meeting 1>", "<decision 2>", ...],
  "action_items_template": ["<action item placeholder 1, e.g. '[Owner] to send X by [date]'>", ...],
  "meeting_summary": "<2-3 sentence description of the meeting purpose, expected outcome, and why it matters>"
}

Agenda construction rules:
- The sum of all agenda item duration_min values MUST equal the total_duration_min provided
- Always include an opening/check-in block (2-5 min) and a wrap-up/next steps block (3-5 min)
- Distribute remaining time proportionally across the goals
- Each agenda item needs a clear, measurable desired_outcome — not just a topic label
- Facilitator notes should be practical (e.g. "Use silent brainstorming for first 3 min", "Time-box discussion strictly")

Preparation tips: provide 1-3 specific tips per participant or role. If participants are generic (e.g. "team"), provide tips for "All participants".
Decision points: list 2-4 concrete decisions this meeting must produce.
Action items template: list 2-4 action item formats using [Owner] and [Date] placeholders.
"""


def _normalise_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)] if value else []


def _build_user_message(inp: Dict[str, Any]) -> str:
    title = str(inp.get("title") or "Untitled meeting").strip()
    duration_min = int(inp.get("duration_min") or 30)
    participants = _normalise_list(inp.get("participants"))
    goals = _normalise_list(inp.get("goals"))
    meeting_type = str(inp.get("meeting_type") or "").strip()
    context = str(inp.get("context") or "").strip()

    parts = [
        f"Meeting title: {title}",
        f"Total duration: {duration_min} minutes",
    ]

    if meeting_type:
        parts.append(f"Meeting type: {meeting_type}")

    if participants:
        parts.append(f"Participants: {', '.join(participants)}")
    else:
        parts.append("Participants: (not specified)")

    if goals:
        parts.append("Goals / topics:")
        for g in goals:
            parts.append(f"  - {g}")
    else:
        parts.append("Goals: (not specified — generate a general structured agenda)")

    if context:
        parts.append(f"\nBackground context:\n{context[:2000]}")

    parts.append(f"\nIMPORTANT: agenda duration_min values must sum to exactly {duration_min}.")

    return "\n".join(parts)


def _parse_llm_response(
    content: str,
    title: str,
    duration_min: int,
    participants: List[str],
) -> Dict[str, Any]:
    data = json.loads(content)

    # Build agenda blocks and compute start_min cumulatively
    raw_agenda = data.get("agenda") or []
    if not isinstance(raw_agenda, list):
        raw_agenda = []

    agenda: List[Dict[str, Any]] = []
    running = 0
    total_assigned = 0

    for item in raw_agenda:
        if not isinstance(item, dict):
            continue
        try:
            dur = max(1, int(item.get("duration_min") or 5))
        except (TypeError, ValueError):
            dur = 5
        agenda.append({
            "start_min": running,
            "duration_min": dur,
            "topic": str(item.get("topic") or ""),
            "desired_outcome": str(item.get("desired_outcome") or ""),
            "facilitator_notes": str(item.get("facilitator_notes") or ""),
        })
        running += dur
        total_assigned += dur

    # If the LLM's durations don't sum to the target, stretch the last block
    if agenda and total_assigned != duration_min:
        diff = duration_min - total_assigned
        agenda[-1]["duration_min"] = max(1, agenda[-1]["duration_min"] + diff)

    def _as_str_list(val: Any) -> List[str]:
        if not isinstance(val, list):
            return []
        return [str(v) for v in val if v]

    prep_raw = data.get("preparation_tips") or []
    if not isinstance(prep_raw, list):
        prep_raw = []
    preparation_tips = [
        {
            "participant": str(p.get("participant") or ""),
            "tips": _as_str_list(p.get("tips")),
        }
        for p in prep_raw
        if isinstance(p, dict)
    ]

    return {
        "title": title,
        "duration_min": duration_min,
        "participants": participants,
        "agenda": agenda,
        "preparation_tips": preparation_tips,
        "decision_points": _as_str_list(data.get("decision_points")),
        "action_items_template": _as_str_list(data.get("action_items_template")),
        "meeting_summary": str(data.get("meeting_summary") or ""),
    }


def _fallback_agenda(title: str, duration_min: int, participants: List[str], reason: str) -> Dict[str, Any]:
    wrap = min(5, duration_min)
    main = duration_min - wrap
    return {
        "title": title,
        "duration_min": duration_min,
        "participants": participants,
        "agenda": [
            {"start_min": 0, "duration_min": main, "topic": "Discussion",
             "desired_outcome": "", "facilitator_notes": ""},
            {"start_min": main, "duration_min": wrap, "topic": "Wrap-up / Actions",
             "desired_outcome": "", "facilitator_notes": ""},
        ],
        "preparation_tips": [],
        "decision_points": [],
        "action_items_template": [],
        "meeting_summary": f"Automated agenda generation could not be completed: {reason}",
    }


def meeting_agenda_assistant(
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    inp = (payload or {}).get("input") or {}

    title = str(inp.get("title") or "Meeting").strip()
    duration_min = int(inp.get("duration_min") or 30)
    participants = _normalise_list(inp.get("participants"))

    agenda_id = f"MA-{uuid4().hex[:10].upper()}"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("meeting_agenda_assistant: OPENAI_API_KEY not set — returning degraded response")
        result = _fallback_agenda(title, duration_min, participants, "OPENAI_API_KEY not configured")
        return {
            "status": "degraded",
            "agenda_id": agenda_id,
            **result,
            "degraded_reason": "OPENAI_API_KEY not configured",

            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(inp)

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1500,
        )

        raw_content = response.choices[0].message.content or ""
        result = _parse_llm_response(raw_content, title, duration_min, participants)

        logger.info(
            "meeting_agenda_assistant: LLM call succeeded — agenda_id=%s blocks=%d decisions=%d",
            agenda_id,
            len(result["agenda"]),
            len(result["decision_points"]),
        )

        return {
            "status": "ok",
            "agenda_id": agenda_id,
            **result,
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,

            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("meeting_agenda_assistant: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("meeting_agenda_assistant: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("meeting_agenda_assistant: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("meeting_agenda_assistant: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("meeting_agenda_assistant: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    result = _fallback_agenda(title, duration_min, participants, reason)
    return {
        "status": "degraded",
        "agenda_id": agenda_id,
        **result,
        "degraded_reason": reason,
        "user_id": user_id,
    }


run = meeting_agenda_assistant
