from typing import Any, Dict, List, Optional


def _score_candidate(candidate_name: str, role: str) -> int:
    score = 50

    if candidate_name:
        score += 15
    if role:
        score += 20

    role_lower = role.lower()
    if "manager" in role_lower:
        score += 10
    if "operations" in role_lower:
        score += 5

    return min(score, 100)


def hr_recruitment(payload: Dict[str, Any], user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}
    user = payload.get("user")

    candidate_name = str(input_data.get("candidate_name", "") or "").strip()
    role = str(input_data.get("role", "") or "").strip()

    score = _score_candidate(candidate_name, role)

    if score >= 80:
        recommendation = "strong_review"
    elif score >= 65:
        recommendation = "review"
    else:
        recommendation = "hold"

    candidates: List[Dict[str, Any]] = []
    if candidate_name or role:
        candidates.append(
            {
                "name": candidate_name or "Unknown candidate",
                "role": role or "Unknown role",
                "score": score,
                "recommendation": recommendation,
            }
        )

    summary = (
        f"Processed recruitment input for "
        f"{candidate_name if candidate_name else 'an unspecified candidate'}"
        f"{f' applying for {role}' if role else ''}. "
        f"Recommendation: {recommendation.replace('_', ' ')}."
    )

    return {
        "status": "ok",
        "candidates": candidates,
        "summary": summary,
        "received": {
            "input": input_data,
            "context": context,
            "user": user,
            "org_id": org_id,
        },
        "user_id": user_id,
    }


run = hr_recruitment
