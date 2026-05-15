"""
Business Intelligence workflow — LLM implementation.

Input fields (all optional):
  question           : The business question to analyse
  context_data       : Additional context (revenue figures, team size, sector, etc.)
  time_period        : Relevant time period (e.g. "Q1 2024", "last 6 months")
  company_size       : Company size indicator (e.g. "50 employees", "€5M revenue")

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  insights:
    focus_area       : Identified business domain
    question_received: The original question
    summary          : Strategic narrative answering the question
    kpis             : list[str] — relevant KPIs to track
    recommendations  : list[str] — actionable strategic recommendations
    priority_level   : "high" | "medium" | "low"
    action_items     : list[str] — concrete immediate next steps
    risks            : list[str] — key risks to be aware of
  summary            : Mirror of insights.summary
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an enterprise business intelligence AI for SME companies. Provide strategic, actionable insights based on the question asked.

Analyse the business question and return a structured JSON intelligence report.
Return valid JSON only — no prose, no markdown.

Required JSON schema:
{
  "focus_area": "<primary business domain: sales | finance | customer | operations | marketing | hr | strategy | general>",
  "summary": "<3-4 sentence strategic answer to the question with concrete insights>",
  "kpis": ["<most relevant KPI for this question 1>", "<KPI 2>", "<KPI 3>", ...],
  "recommendations": ["<strategic recommendation 1>", "<recommendation 2>", "<recommendation 3>", ...],
  "priority_level": <"high" | "medium" | "low">,
  "action_items": ["<concrete immediate next step 1>", "<step 2>", ...],
  "risks": ["<key risk or blind spot 1>", "<risk 2>", ...]
}

Priority level guidance:
- "high"  : Urgent issue, significant revenue or operational impact, act within days
- "medium": Important but not urgent, plan within the quarter
- "low"   : Informational, strategic horizon, monitor over time

KPI guidance: provide 3-6 KPIs that are directly measurable and relevant to the specific question.
Recommendations: provide 3-5 strategic recommendations, each specific and actionable (not generic advice).
Action items: provide 2-4 concrete steps the business can take in the next 30 days.
Risks: identify 2-3 risks or blind spots relevant to the question and context.

If no question is provided, produce a general SME business health baseline assessment.
"""


def _build_user_message(input_data: Dict[str, Any], context: Dict[str, Any]) -> str:
    parts: List[str] = []

    question = str(input_data.get("question") or "").strip()
    parts.append(f"Business question: {question or 'No specific question — provide a general baseline assessment.'}")

    company_size = str(input_data.get("company_size") or context.get("company_size") or "").strip()
    if company_size:
        parts.append(f"Company size: {company_size}")

    time_period = str(input_data.get("time_period") or "").strip()
    if time_period:
        parts.append(f"Time period: {time_period}")

    context_data = str(input_data.get("context_data") or "").strip()
    if context_data:
        parts.append(f"\nAdditional context:\n{context_data[:3000]}")

    return "\n".join(parts)


def _parse_llm_response(content: str, question: str) -> Dict[str, Any]:
    data = json.loads(content)

    focus_area = str(data.get("focus_area") or "general").lower()
    valid_areas = {"sales", "finance", "customer", "operations", "marketing", "hr", "strategy", "general"}
    if focus_area not in valid_areas:
        focus_area = "general"

    priority_level = data.get("priority_level", "medium")
    if priority_level not in {"high", "medium", "low"}:
        priority_level = "medium"

    def _as_str_list(val: Any) -> List[str]:
        if not isinstance(val, list):
            return []
        return [str(v) for v in val if v]

    return {
        "focus_area": focus_area,
        "question_received": question or "No question provided",
        "summary": str(data.get("summary") or ""),
        "kpis": _as_str_list(data.get("kpis")),
        "recommendations": _as_str_list(data.get("recommendations")),
        "priority_level": priority_level,
        "action_items": _as_str_list(data.get("action_items")),
        "risks": _as_str_list(data.get("risks")),
    }


def _fallback_insights(question: str, reason: str) -> Dict[str, Any]:
    return {
        "focus_area": "general",
        "question_received": question or "No question provided",
        "summary": f"Automated business intelligence analysis could not be completed: {reason}",
        "kpis": [],
        "recommendations": ["Manual analysis required — automated insights unavailable."],
        "priority_level": "medium",
        "action_items": [],
        "risks": [],
    }


def business_intelligence(
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}
    user = payload.get("user")

    question = str(input_data.get("question") or "").strip()


    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("business_intelligence: OPENAI_API_KEY not set — returning degraded response")
        insights = _fallback_insights(question, "OPENAI_API_KEY not configured")
        return {
            "status": "degraded",
            "insights": insights,
            "summary": insights["summary"],
            "degraded_reason": "OPENAI_API_KEY not configured",

            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(input_data, context)

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1200,
        )

        raw_content = response.choices[0].message.content or ""
        insights = _parse_llm_response(raw_content, question)

        logger.info(
            "business_intelligence: LLM call succeeded — focus=%s priority=%s kpis=%d recommendations=%d",
            insights["focus_area"],
            insights["priority_level"],
            len(insights["kpis"]),
            len(insights["recommendations"]),
        )

        return {
            "status": "ok",
            "insights": insights,
            "summary": insights["summary"],
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,

            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("business_intelligence: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("business_intelligence: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("business_intelligence: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("business_intelligence: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("business_intelligence: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    insights = _fallback_insights(question, reason)
    return {
        "status": "degraded",
        "insights": insights,
        "summary": insights["summary"],
        "degraded_reason": reason,
        "user_id": user_id,
    }


run = business_intelligence
