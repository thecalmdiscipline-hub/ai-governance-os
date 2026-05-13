"""
HR Recruitment workflow — LLM implementation.

Input fields (all optional):
  candidate_name     : Full name of the candidate
  role               : Job title / position being applied for
  resume             : CV or resume text
  cv                 : Alias for resume
  experience         : Years of experience or experience description
  skills             : List or comma-separated string of skills
  education          : Educational background
  motivation         : Cover letter or motivation text
  notes              : Recruiter notes or observations

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  candidates         : list[{name, role, score, recommendation, strengths, concerns, interview_questions}]
  summary            : str — brief narrative on the candidate's overall fit
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an enterprise HR recruitment AI. Evaluate candidates professionally and objectively based on experience, skills, and culture fit.

Analyse the provided candidate information and return a structured JSON assessment.
Return valid JSON only — no prose, no markdown.

Required JSON schema:
{
  "score": <integer 0-100, where 100 = perfect fit for the role>,
  "recommendation": <"strong_yes" | "yes" | "maybe" | "no">,
  "strengths": ["<key strength 1>", "<strength 2>", ...],
  "concerns": ["<concern or gap 1>", "<concern 2>", ...],
  "interview_questions": ["<targeted interview question 1>", "<question 2>", ...],
  "summary": "<2-3 sentence assessment of overall fit and standout factors>"
}

Scoring guidance:
- 85-100: Strong yes — exceptional fit, prioritise interview immediately
- 65-84 : Yes — good fit, proceed to interview
- 40-64 : Maybe — partial fit, screen further or consider for alternative role
- 0-39  : No — significant gaps, does not meet minimum requirements

Recommendation must match the score:
- score >= 85  → "strong_yes"
- score 65-84  → "yes"
- score 40-64  → "maybe"
- score < 40   → "no"

Evaluation criteria (weighted):
1. Relevant experience for the role (40%)
2. Required skills match (30%)
3. Education and credentials (15%)
4. Motivation and culture fit signals (15%)

Provide 3-5 targeted interview questions that address the specific candidate's profile and any gaps.
If critical information is missing (no CV, no experience described), reflect that in the score and concerns.
"""


def _normalise_skills(skills: Any) -> str:
    if not skills:
        return ""
    if isinstance(skills, list):
        return ", ".join(str(s) for s in skills)
    return str(skills)


def _build_user_message(input_data: Dict[str, Any]) -> str:
    parts: List[str] = ["Candidate information:"]

    fields = [
        ("Name", input_data.get("candidate_name")),
        ("Role applied for", input_data.get("role")),
        ("Experience", input_data.get("experience")),
        ("Skills", _normalise_skills(input_data.get("skills"))),
        ("Education", input_data.get("education")),
    ]

    for label, value in fields:
        if value:
            parts.append(f"  {label}: {value}")

    resume = str(input_data.get("resume") or input_data.get("cv") or "").strip()
    if resume:
        parts.append(f"\nCV / Resume:\n{resume[:5000]}")

    motivation = str(input_data.get("motivation") or "").strip()
    if motivation:
        parts.append(f"\nMotivation / Cover letter:\n{motivation[:2000]}")

    notes = str(input_data.get("notes") or "").strip()
    if notes:
        parts.append(f"\nRecruiter notes:\n{notes[:1000]}")

    if len(parts) == 1:
        parts.append("  (no candidate details provided)")

    return "\n".join(parts)


def _parse_llm_response(content: str, candidate_name: str, role: str) -> Dict[str, Any]:
    data = json.loads(content)

    score = max(0, min(100, int(data.get("score", 50))))

    recommendation = data.get("recommendation", "maybe")
    if recommendation not in {"strong_yes", "yes", "maybe", "no"}:
        recommendation = "maybe"

    strengths = data.get("strengths", [])
    if not isinstance(strengths, list):
        strengths = []

    concerns = data.get("concerns", [])
    if not isinstance(concerns, list):
        concerns = []

    interview_questions = data.get("interview_questions", [])
    if not isinstance(interview_questions, list):
        interview_questions = []

    return {
        "name": candidate_name or "Unknown candidate",
        "role": role or "Unknown role",
        "score": score,
        "recommendation": recommendation,
        "strengths": [str(s) for s in strengths],
        "concerns": [str(c) for c in concerns],
        "interview_questions": [str(q) for q in interview_questions],
        "summary": str(data.get("summary", "")),
    }


def _fallback_candidate(candidate_name: str, role: str, reason: str) -> Dict[str, Any]:
    return {
        "name": candidate_name or "Unknown candidate",
        "role": role or "Unknown role",
        "score": None,
        "recommendation": "maybe",
        "strengths": [],
        "concerns": [f"Automated assessment unavailable: {reason}"],
        "interview_questions": [],
        "summary": f"Candidate could not be automatically assessed: {reason}",
    }


def hr_recruitment(
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}
    user = payload.get("user")

    candidate_name = str(input_data.get("candidate_name") or "").strip()
    role = str(input_data.get("role") or "").strip()

    received = {
        "input": input_data,
        "context": context,
        "user": user,
        "org_id": org_id,
    }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("hr_recruitment: OPENAI_API_KEY not set — returning degraded response")
        candidate = _fallback_candidate(candidate_name, role, "OPENAI_API_KEY not configured")
        return {
            "status": "degraded",
            "candidates": [candidate] if (candidate_name or role) else [],
            "summary": candidate["summary"],
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
            max_tokens=1000,
        )

        raw_content = response.choices[0].message.content or ""
        candidate = _parse_llm_response(raw_content, candidate_name, role)

        logger.info(
            "hr_recruitment: LLM call succeeded — candidate=%s role=%s score=%s recommendation=%s",
            candidate["name"],
            candidate["role"],
            candidate["score"],
            candidate["recommendation"],
        )

        return {
            "status": "ok",
            "candidates": [candidate],
            "summary": candidate["summary"],
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,
            "received": received,
            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("hr_recruitment: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("hr_recruitment: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("hr_recruitment: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("hr_recruitment: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("hr_recruitment: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    candidate = _fallback_candidate(candidate_name, role, reason)
    return {
        "status": "degraded",
        "candidates": [candidate] if (candidate_name or role) else [],
        "summary": candidate["summary"],
        "degraded_reason": reason,
        "received": received,
        "user_id": user_id,
    }


run = hr_recruitment
