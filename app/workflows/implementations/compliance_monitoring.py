"""
Compliance Monitoring workflow — LLM pilot implementation.

Input fields (all optional):
  policy_text        : The policy, procedure or document to audit
  control_area       : Compliance domain, e.g. "data governance", "model transparency"
  current_findings   : Existing findings or observations to consider
  organization_name  : Name of the organisation (for context)
  framework          : Target framework, e.g. "ISO 42001", "EU AI Act", "GDPR"

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  compliance_score   : 0-100
  risk_level         : "low" | "medium" | "high" | "critical"
  issues_found       : int
  findings           : list[{issue, severity, recommendation}]
  recommendations    : list[str]
  framework_alignment: list[str]
  summary            : str
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an AI governance and compliance auditor specialising in:
- ISO/IEC 42001 (AI Management Systems)
- EU AI Act (risk classification and conformity requirements)
- GDPR (data protection for AI systems)
- Internal AI governance policies

Your task is to analyse the provided compliance input and return a structured JSON
audit report. Be precise, actionable and risk-aware. Always return valid JSON matching
the schema below — no prose, no markdown, only JSON.

Required JSON schema:
{
  "compliance_score": <integer 0-100, 100 = fully compliant>,
  "risk_level": <"low" | "medium" | "high" | "critical">,
  "issues_found": <integer count of distinct issues>,
  "findings": [
    {
      "issue": "<concise description of the compliance gap>",
      "severity": <"low" | "medium" | "high" | "critical">,
      "framework_ref": "<relevant standard or article, e.g. ISO 42001 §6.1>",
      "recommendation": "<specific corrective action>"
    }
  ],
  "recommendations": ["<high-level recommendation 1>", ...],
  "framework_alignment": ["<framework name>", ...],
  "summary": "<2-3 sentence executive summary of the compliance posture>"
}

Scoring guidance:
- 90-100: Minor or no gaps, strong governance posture
- 70-89:  Moderate gaps, corrective actions underway or feasible short-term
- 50-69:  Significant gaps, structured remediation programme required
- 0-49:   Critical non-compliance, immediate action required
"""


def _build_user_message(input_data: Dict[str, Any], context: Dict[str, Any]) -> str:
    parts: List[str] = []

    org = str(input_data.get("organization_name") or context.get("organization_name") or "").strip()
    if org:
        parts.append(f"Organisation: {org}")

    framework = str(input_data.get("framework") or "").strip()
    if framework:
        parts.append(f"Target framework: {framework}")

    control_area = str(input_data.get("control_area") or "").strip()
    if control_area:
        parts.append(f"Control area: {control_area}")

    policy_text = str(input_data.get("policy_text") or "").strip()
    if policy_text:
        parts.append(f"\nPolicy / document to audit:\n{policy_text[:6000]}")

    findings = str(input_data.get("current_findings") or "").strip()
    if findings:
        parts.append(f"\nExisting findings / observations:\n{findings[:2000]}")

    if not parts:
        parts.append(
            "No specific input provided. Produce a generic AI governance "
            "compliance baseline assessment."
        )

    return "\n".join(parts)


def _parse_llm_response(content: str) -> Dict[str, Any]:
    data = json.loads(content)

    score = max(0, min(100, int(data.get("compliance_score", 50))))
    risk = data.get("risk_level", "medium")
    if risk not in {"low", "medium", "high", "critical"}:
        risk = "medium"

    findings = data.get("findings", [])
    if not isinstance(findings, list):
        findings = []

    recommendations = data.get("recommendations", [])
    if not isinstance(recommendations, list):
        recommendations = []

    framework_alignment = data.get("framework_alignment", [])
    if not isinstance(framework_alignment, list):
        framework_alignment = []

    return {
        "compliance_score": score,
        "risk_level": risk,
        "issues_found": len(findings),
        "findings": findings,
        "recommendations": recommendations,
        "framework_alignment": framework_alignment,
        "summary": str(data.get("summary", "")),
    }


def _fallback_response(reason: str) -> Dict[str, Any]:
    return {
        "compliance_score": None,
        "risk_level": "unknown",
        "issues_found": 0,
        "findings": [],
        "recommendations": ["Manual review required — automated analysis unavailable."],
        "framework_alignment": [],
        "summary": f"Automated compliance analysis could not be completed: {reason}",
        "degraded_reason": reason,
    }


def compliance_monitoring(
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("compliance_monitoring: OPENAI_API_KEY not set — returning degraded response")
        output = _fallback_response("OPENAI_API_KEY not configured")
        return {"status": "degraded", **output}

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
            temperature=0.2,
            max_tokens=1500,
        )

        raw_content = response.choices[0].message.content or ""
        output = _parse_llm_response(raw_content)

        logger.info(
            "compliance_monitoring: LLM call succeeded — score=%s risk=%s issues=%d",
            output["compliance_score"],
            output["risk_level"],
            output["issues_found"],
        )

        return {
            "status": "ok",
            **output,
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,
        }

    except openai.RateLimitError:
        logger.warning("compliance_monitoring: OpenAI rate limit reached")
        return {"status": "degraded", **_fallback_response("OpenAI rate limit reached — retry later")}

    except openai.APIConnectionError as exc:
        logger.warning("compliance_monitoring: OpenAI connection error: %s", exc)
        return {"status": "degraded", **_fallback_response(f"Could not reach OpenAI API: {exc}")}

    except openai.APIStatusError as exc:
        logger.warning("compliance_monitoring: OpenAI API error %s: %s", exc.status_code, exc.message)
        return {"status": "degraded", **_fallback_response(f"OpenAI API error {exc.status_code}")}

    except json.JSONDecodeError as exc:
        logger.error("compliance_monitoring: Failed to parse LLM JSON response: %s", exc)
        return {"status": "degraded", **_fallback_response("LLM returned unparseable response")}

    except Exception as exc:
        logger.error("compliance_monitoring: Unexpected error: %s", exc, exc_info=True)
        return {"status": "degraded", **_fallback_response(f"Unexpected error: {type(exc).__name__}")}


run = compliance_monitoring
