"""
Customer Support workflow — LLM implementation.

Input fields (all optional):
  issue              : Description of the customer's problem
  ping               : Alias for issue
  priority           : Caller-supplied priority hint (overridden by AI triage)
  customer_name      : Name of the customer or contact
  product            : Product or service the issue relates to

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  ticket_id          : Unique ticket ID (CS-xxxx)
  triage:
    issue            : Normalised issue description
    priority         : "low" | "medium" | "high" | "critical"
    urgency_reason   : Why this urgency level was assigned
    suggested_action : Concrete next step for the support agent
    summary          : Brief executive summary of the problem
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an enterprise customer support AI that helps business clients with professional, concise responses.

Analyse the reported issue and return a structured JSON triage report. Be precise, actionable and empathetic.
Return valid JSON only — no prose, no markdown.

Required JSON schema:
{
  "priority": <"low" | "medium" | "high" | "critical">,
  "urgency_reason": "<one sentence explaining why this priority was assigned>",
  "suggested_action": "<concrete next step for the support agent, e.g. escalate to engineering, send workaround, schedule call>",
  "summary": "<2-3 sentence summary of the problem and its business impact>"
}

Priority guidance:
- "critical" : System down, data loss, security breach, complete business blockage
- "high"     : Major feature broken, significant workflow disruption, SLA at risk
- "medium"   : Partial degradation, workaround available, moderate impact
- "low"      : Minor issue, cosmetic problem, general question or feature request
"""


def _build_user_message(input_data: Dict[str, Any]) -> str:
    parts: list[str] = []

    customer = str(input_data.get("customer_name") or "").strip()
    if customer:
        parts.append(f"Customer: {customer}")

    product = str(input_data.get("product") or "").strip()
    if product:
        parts.append(f"Product / service: {product}")

    priority_hint = str(input_data.get("priority") or "").strip()
    if priority_hint:
        parts.append(f"Caller-supplied priority hint: {priority_hint}")

    issue = str(input_data.get("issue") or input_data.get("ping") or "").strip()
    parts.append(f"\nIssue description:\n{issue or 'No description provided.'}")

    return "\n".join(parts)


def _parse_llm_response(content: str, issue: str) -> Dict[str, Any]:
    data = json.loads(content)

    priority = data.get("priority", "medium")
    if priority not in {"low", "medium", "high", "critical"}:
        priority = "medium"

    return {
        "issue": issue or "No description provided.",
        "priority": priority,
        "urgency_reason": str(data.get("urgency_reason", "")),
        "suggested_action": str(data.get("suggested_action", "")),
        "summary": str(data.get("summary", "")),
    }


def _fallback_triage(issue: str, reason: str) -> Dict[str, Any]:
    return {
        "issue": issue or "unknown_issue",
        "priority": "medium",
        "urgency_reason": f"Automated triage unavailable: {reason}",
        "suggested_action": "Manual review required — automated analysis could not be completed.",
        "summary": f"A support request was received but could not be automatically analysed: {reason}",
    }


def run(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}
    user = payload.get("user")

    issue = str(input_data.get("issue") or input_data.get("ping") or "").strip()
    ticket_id = f"CS-{uuid4().hex[:10].upper()}"

    received = {
        "input": input_data,
        "context": context,
        "user": user,
    }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("customer_support: OPENAI_API_KEY not set — returning degraded response")
        return {
            "status": "degraded",
            "ticket_id": ticket_id,
            "triage": _fallback_triage(issue, "OPENAI_API_KEY not configured"),
            "degraded_reason": "OPENAI_API_KEY not configured",
            "received": received,
            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(input_data)

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=600,
        )

        raw_content = response.choices[0].message.content or ""
        triage = _parse_llm_response(raw_content, issue)

        logger.info(
            "customer_support: LLM call succeeded — ticket=%s priority=%s",
            ticket_id,
            triage["priority"],
        )

        return {
            "status": "ok",
            "ticket_id": ticket_id,
            "triage": triage,
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,
            "received": received,
            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("customer_support: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("customer_support: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("customer_support: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("customer_support: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("customer_support: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    return {
        "status": "degraded",
        "ticket_id": ticket_id,
        "triage": _fallback_triage(issue, reason),
        "degraded_reason": reason,
        "received": received,
        "user_id": user_id,
    }
