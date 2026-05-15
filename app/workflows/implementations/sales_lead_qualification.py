"""
Sales Lead Qualification workflow — LLM implementation.

Input fields (all optional, nested under input.lead):
  lead.company       : Company name
  lead.email         : Contact email address
  lead.name          : Contact full name
  lead.title         : Job title / role
  lead.industry      : Industry sector
  lead.revenue       : Reported or estimated annual revenue
  lead.employees     : Company headcount
  lead.website       : Company website
  lead.pain_points   : Described pain points or use case
  source / channel   : Lead origin (inbound, referral, outbound, …)

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  workflow           : "sales_lead_qualification"
  qualification      : "qualified" | "needs_nurturing" | "unqualified"
  score              : 0-100 (AI-determined fit score)
  next_actions       : list[str] — concrete recommended steps
  strengths          : list[str] — strongest signals for this lead
  weaknesses         : list[str] — gaps or risk factors
  summary            : str — brief narrative on the lead
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are a B2B sales qualification AI for enterprise companies with €1M+ annual revenue.
Your job is to evaluate inbound and outbound leads based on buying readiness, budget fit, and ideal customer profile (ICP) alignment.

Analyse the provided lead information and return a structured JSON qualification report.
Return valid JSON only — no prose, no markdown.

Required JSON schema:
{
  "score": <integer 0-100, where 100 = perfect ICP fit with immediate buying intent>,
  "qualification": <"qualified" | "needs_nurturing" | "unqualified">,
  "summary": "<2-3 sentence narrative on why this lead is or isn't a strong fit>",
  "strengths": ["<strongest positive signal 1>", "<signal 2>", ...],
  "weaknesses": ["<biggest gap or risk factor 1>", "<gap 2>", ...],
  "next_actions": ["<concrete recommended action 1>", "<action 2>", ...]
}

Scoring guidance:
- 80-100: Qualified — strong ICP match, clear budget/authority, act immediately
- 50-79 : Needs nurturing — partial fit, missing information, or unclear timeline
- 0-49  : Unqualified — poor fit, no budget signal, outside ICP

Qualification thresholds must match the score:
- score >= 80  → "qualified"
- score 50-79  → "needs_nurturing"
- score < 50   → "unqualified"

Focus on: company size, revenue signals, seniority of contact, explicit pain points, lead source quality, and any buying urgency indicators.
If critical information is missing, reflect that as a weakness and factor it into the score.
"""


_PAYLOAD_META_KEYS = {"user", "context", "org_id", "lead", "input", "source", "channel"}


def _build_user_message(inp: Dict[str, Any], payload: Dict[str, Any]) -> str:
    lead = inp.get("lead") or payload.get("lead") or {}

    # Search lead dict → inp dict → payload root (handles all nesting variants)
    def _get(key: str) -> Any:
        return lead.get(key) or inp.get(key) or payload.get(key)

    parts: List[str] = ["Lead information:"]

    fields = [
        ("Company", _get("company")),
        ("Contact name", _get("name")),
        ("Job title", _get("title")),
        ("Email", _get("email")),
        ("Industry", _get("industry")),
        ("Annual revenue", _get("revenue")),
        ("Employees", _get("employees")),
        ("Website", _get("website")),
        ("Lead source", _get("source") or _get("channel")),
        ("Pain points / use case", _get("pain_points")),
    ]

    for label, value in fields:
        if value:
            parts.append(f"  {label}: {value}")

    # Merge all available data layers and send as raw JSON so the model sees
    # everything regardless of nesting — this is the authoritative data block.
    merged: Dict[str, Any] = {}
    for layer in (payload, inp, lead):
        for k, v in layer.items():
            if k not in _PAYLOAD_META_KEYS and v is not None and v != "":
                merged[k] = v

    if merged:
        parts.append(
            f"\nComplete input data (JSON):\n"
            f"{json.dumps(merged, ensure_ascii=False, indent=2)}"
        )
    elif len(parts) == 1:
        parts.append("  (no lead details provided)")

    logger.debug("sales_lead_qualification: user message built:\n%s", "\n".join(parts))
    return "\n".join(parts)


def _parse_score(raw: Any) -> int:
    """Safely parse score from LLM output.

    Handles: int, float, string, null/None.
    LLMs occasionally return 0.85 instead of 85 — values ≤ 1.0 are scaled up.
    Falls back to 50 if the value is missing or unparseable.
    """
    if raw is None:
        logger.warning("sales_lead_qualification: score field is null — defaulting to 50")
        return 50
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("sales_lead_qualification: could not parse score %r — defaulting to 50", raw)
        return 50
    if 0.0 < value <= 1.0:
        # LLM returned a 0-1 decimal instead of 0-100 integer
        logger.warning(
            "sales_lead_qualification: score %r looks like a 0-1 decimal — scaling to %d",
            raw, round(value * 100),
        )
        value = value * 100
    return max(0, min(100, round(value)))


def _qualify(score: int) -> str:
    if score >= 80:
        return "qualified"
    if score >= 50:
        return "needs_nurturing"
    return "unqualified"


def _parse_llm_response(content: str) -> Dict[str, Any]:
    logger.debug("sales_lead_qualification: raw LLM response: %s", content)
    data = json.loads(content)

    score = _parse_score(data.get("score"))
    # Always derive qualification from score — never trust the LLM label directly
    qualification = _qualify(score)

    strengths = data.get("strengths", [])
    if not isinstance(strengths, list):
        strengths = []

    weaknesses = data.get("weaknesses", [])
    if not isinstance(weaknesses, list):
        weaknesses = []

    next_actions = data.get("next_actions", [])
    if not isinstance(next_actions, list):
        next_actions = []

    return {
        "score": score,
        "qualification": qualification,
        "summary": str(data.get("summary", "")),
        "strengths": [str(s) for s in strengths],
        "weaknesses": [str(w) for w in weaknesses],
        "next_actions": [str(a) for a in next_actions],
    }


def _fallback_result(reason: str) -> Dict[str, Any]:
    return {
        "score": None,
        "qualification": "needs_nurturing",
        "summary": f"Automated lead qualification could not be completed: {reason}",
        "strengths": [],
        "weaknesses": ["Manual review required — automated analysis unavailable."],
        "next_actions": ["Manually review lead and assign to sales representative."],
    }


def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = payload.get("input") or {}

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("sales_lead_qualification: OPENAI_API_KEY not set — returning degraded response")
        return {
            "workflow": "sales_lead_qualification",
            "status": "degraded",
            **_fallback_result("OPENAI_API_KEY not configured"),
            "degraded_reason": "OPENAI_API_KEY not configured",

            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(inp, payload)

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=800,
        )

        raw_content = response.choices[0].message.content or ""
        result = _parse_llm_response(raw_content)

        logger.info(
            "sales_lead_qualification: LLM call succeeded — score=%s qualification=%s",
            result["score"],
            result["qualification"],
        )

        return {
            "workflow": "sales_lead_qualification",
            "status": "ok",
            **result,
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,

            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("sales_lead_qualification: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("sales_lead_qualification: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("sales_lead_qualification: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("sales_lead_qualification: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("sales_lead_qualification: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    return {
        "workflow": "sales_lead_qualification",
        "status": "degraded",
        **_fallback_result(reason),
        "degraded_reason": reason,
        "user_id": user_id,
    }
