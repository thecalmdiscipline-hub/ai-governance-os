"""
Marketing Automation workflow — LLM implementation.

Input fields (all optional):
  campaign           : Campaign name or description
  audience           : Target audience description
  product            : Product or service being marketed
  goals              : Campaign goals (brand awareness, lead gen, conversion, etc.)
  budget             : Approximate budget indicator (e.g. "€5k", "limited", "enterprise")
  industry           : Industry sector of the target audience
  current_channels   : Channels already in use

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  campaign           : Campaign name (echoed)
  audience           : Target audience (echoed)
  actions            : list[str] — recommended marketing actions
  strategy           : {summary, messaging, channels}
  timing             : {launch_recommendation, frequency, duration}
  roi_estimate       : {direction, rationale, expected_metrics}

PII handling: the user message (campaign brief) is anonymised via
app.core.pii_anonymizer before being sent to OpenAI. The LLM-generated
free-text fields (actions, strategy.summary/messaging/channels, timing.*,
roi_estimate.rationale/expected_metrics) can echo an anonymization
placeholder back, so each is run through
pii_anonymizer.restore_placeholders() before being returned — safe
because it only reveals the requester's own submitted data back into the
same request (see app/core/pii_anonymizer.py and CLAUDE.md §6). The
top-level campaign/audience fields are the raw, never-anonymized input
values echoed straight back, so they need no restore.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.core import pii_anonymizer

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an enterprise marketing automation AI for B2B companies. Generate data-driven, professional marketing strategies.

Analyse the provided campaign brief and return a structured JSON marketing strategy.
Return valid JSON only — no prose, no markdown.

Required JSON schema:
{
  "strategy_summary": "<3-4 sentence B2B marketing strategy tailored to the campaign and audience>",
  "channels": ["<most effective channel 1>", "<channel 2>", ...],
  "actions": ["<concrete marketing action 1>", "<action 2>", ...],
  "messaging": {
    "headline": "<compelling campaign headline>",
    "value_proposition": "<core value proposition for this audience>",
    "call_to_action": "<primary CTA, e.g. 'Request a demo', 'Download the guide'>"
  },
  "timing": {
    "launch_recommendation": "<when to launch, e.g. 'Start on Monday, avoid Q4 holiday weeks'>",
    "frequency": "<contact frequency, e.g. '2x per week for email, daily for LinkedIn'>",
    "duration": "<recommended campaign duration, e.g. '6-week nurture sequence'>"
  },
  "roi_estimate": {
    "direction": <"high" | "medium" | "low">,
    "rationale": "<1-2 sentences on why this ROI direction is expected>",
    "expected_metrics": ["<key metric to track 1>", "<metric 2>", "<metric 3>"]
  }
}

ROI direction guidance:
- "high"  : Strong audience-channel fit, clear buying intent signals, proven tactic for this segment
- "medium": Reasonable fit, standard B2B approach, results depend on execution quality
- "low"   : Broad/unclear audience, mismatched channel, or very long sales cycle with uncertain attribution

Channel options to consider: email_sequence, linkedin_ads, linkedin_organic, content_marketing,
webinar, cold_outreach, retargeting_ads, seo_content, case_studies, partner_marketing, events.

Provide 3-6 channels and 4-6 concrete actions. Actions should be specific enough to assign to a team member.
If budget or audience is vague, reflect that uncertainty in the ROI rationale.
"""


def _build_user_message(inp: Dict[str, Any]) -> str:
    parts: List[str] = ["Campaign brief:"]

    fields = [
        ("Campaign name / description", inp.get("campaign")),
        ("Target audience", inp.get("audience")),
        ("Product / service", inp.get("product")),
        ("Campaign goals", inp.get("goals")),
        ("Budget", inp.get("budget")),
        ("Industry / sector", inp.get("industry")),
        ("Current channels in use", inp.get("current_channels")),
    ]

    for label, value in fields:
        if value:
            parts.append(f"  {label}: {value}")

    if len(parts) == 1:
        parts.append("  (no campaign details provided — generate a general B2B marketing strategy)")

    return "\n".join(parts)


def _parse_llm_response(content: str, campaign: str, audience: str) -> Dict[str, Any]:
    data = json.loads(content)

    def _as_str_list(val: Any) -> List[str]:
        if not isinstance(val, list):
            return []
        return [str(v) for v in val if v]

    messaging_raw = data.get("messaging") or {}
    messaging = {
        "headline": str(messaging_raw.get("headline") or ""),
        "value_proposition": str(messaging_raw.get("value_proposition") or ""),
        "call_to_action": str(messaging_raw.get("call_to_action") or ""),
    }

    timing_raw = data.get("timing") or {}
    timing = {
        "launch_recommendation": str(timing_raw.get("launch_recommendation") or ""),
        "frequency": str(timing_raw.get("frequency") or ""),
        "duration": str(timing_raw.get("duration") or ""),
    }

    roi_raw = data.get("roi_estimate") or {}
    roi_direction = roi_raw.get("direction", "medium")
    if roi_direction not in {"high", "medium", "low"}:
        roi_direction = "medium"
    roi_estimate = {
        "direction": roi_direction,
        "rationale": str(roi_raw.get("rationale") or ""),
        "expected_metrics": _as_str_list(roi_raw.get("expected_metrics")),
    }

    return {
        "campaign": campaign or "Unnamed campaign",
        "audience": audience or "General B2B audience",
        "actions": _as_str_list(data.get("actions")),
        "strategy": {
            "summary": str(data.get("strategy_summary") or ""),
            "messaging": messaging,
            "channels": _as_str_list(data.get("channels")),
        },
        "timing": timing,
        "roi_estimate": roi_estimate,
    }


def _restore_pii_in_result(result: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    restore = pii_anonymizer.restore_placeholders
    result = dict(result)
    result["actions"] = [restore(a, mapping) for a in result.get("actions", [])]

    strategy = dict(result.get("strategy") or {})
    strategy["summary"] = restore(strategy.get("summary", ""), mapping)
    strategy["channels"] = [restore(c, mapping) for c in strategy.get("channels", [])]
    messaging = dict(strategy.get("messaging") or {})
    messaging["headline"] = restore(messaging.get("headline", ""), mapping)
    messaging["value_proposition"] = restore(messaging.get("value_proposition", ""), mapping)
    messaging["call_to_action"] = restore(messaging.get("call_to_action", ""), mapping)
    strategy["messaging"] = messaging
    result["strategy"] = strategy

    timing = dict(result.get("timing") or {})
    timing["launch_recommendation"] = restore(timing.get("launch_recommendation", ""), mapping)
    timing["frequency"] = restore(timing.get("frequency", ""), mapping)
    timing["duration"] = restore(timing.get("duration", ""), mapping)
    result["timing"] = timing

    roi_estimate = dict(result.get("roi_estimate") or {})
    roi_estimate["rationale"] = restore(roi_estimate.get("rationale", ""), mapping)
    roi_estimate["expected_metrics"] = [restore(m, mapping) for m in roi_estimate.get("expected_metrics", [])]
    result["roi_estimate"] = roi_estimate

    return result


def _fallback_result(campaign: str, audience: str, reason: str) -> Dict[str, Any]:
    return {
        "campaign": campaign or "Unnamed campaign",
        "audience": audience or "General B2B audience",
        "actions": ["Manual campaign planning required — automated strategy unavailable."],
        "strategy": {
            "summary": f"Automated marketing strategy could not be generated: {reason}",
            "messaging": {"headline": "", "value_proposition": "", "call_to_action": ""},
            "channels": [],
        },
        "timing": {"launch_recommendation": "", "frequency": "", "duration": ""},
        "roi_estimate": {"direction": "medium", "rationale": reason, "expected_metrics": []},
    }


def marketing_automation(
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    inp = (payload or {}).get("input", {}) or {}

    campaign = str(inp.get("campaign") or "").strip() or "default_campaign"
    audience = str(inp.get("audience") or "").strip() or "broad"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("marketing_automation: OPENAI_API_KEY not set — returning degraded response")
        result = _fallback_result(campaign, audience, "OPENAI_API_KEY not configured")
        return {
            "status": "degraded",
            **result,
            "degraded_reason": "OPENAI_API_KEY not configured",

            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(inp)
        user_message, pii_mapping = pii_anonymizer.anonymize_text_with_mapping(
            user_message, workflow="marketing_automation"
        )

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.4,
            max_tokens=1200,
        )

        raw_content = response.choices[0].message.content or ""
        result = _parse_llm_response(raw_content, campaign, audience)
        result = _restore_pii_in_result(result, pii_mapping)

        logger.info(
            "marketing_automation: LLM call succeeded — campaign=%s channels=%d roi=%s",
            result["campaign"],
            len(result["strategy"]["channels"]),
            result["roi_estimate"]["direction"],
        )

        return {
            "status": "ok",
            **result,
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,

            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("marketing_automation: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("marketing_automation: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("marketing_automation: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("marketing_automation: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except pii_anonymizer.PIIAnonymizerUnavailable as exc:
        logger.error("marketing_automation: PII-anonimisering mislukt — LLM-call geblokkeerd: %s", exc)
        reason = str(exc)

    except Exception as exc:
        logger.error("marketing_automation: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    result = _fallback_result(campaign, audience, reason)
    return {
        "status": "degraded",
        **result,
        "degraded_reason": reason,
        "user_id": user_id,
    }


run = marketing_automation
