from typing import Any, Dict, List, Optional


def _infer_focus(question: str) -> str:
    q = question.lower()

    if "sales" in q or "revenue" in q:
        return "sales"
    if "cost" in q or "expense" in q or "margin" in q:
        return "finance"
    if "customer" in q or "support" in q:
        return "customer"
    if "operations" in q or "process" in q:
        return "operations"

    return "general"


def business_intelligence(payload: Dict[str, Any], user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    context = payload.get("context", {}) or {}
    user = payload.get("user")

    question = str(input_data.get("question", "") or "").strip()
    focus = _infer_focus(question)

    insights: Dict[str, Any] = {
        "focus_area": focus,
        "question_received": question or "No question provided",
        "summary": f"Business intelligence processed for focus area: {focus}.",
        "recommendations": [
            "Review current KPI structure",
            "Compare current period versus previous period",
            "Identify top 3 operational improvement opportunities",
        ],
        "priority_level": "medium",
    }

    if focus == "sales":
        insights["kpis"] = ["pipeline growth", "conversion rate", "average deal value"]
    elif focus == "finance":
        insights["kpis"] = ["gross margin", "cost trend", "cash conversion"]
    elif focus == "customer":
        insights["kpis"] = ["response time", "resolution quality", "customer satisfaction"]
    elif focus == "operations":
        insights["kpis"] = ["cycle time", "throughput", "manual workload reduction"]
    else:
        insights["kpis"] = ["growth", "efficiency", "risk"]

    return {
        "status": "ok",
        "insights": insights,
        "summary": insights["summary"],
        "received": {
            "input": input_data,
            "context": context,
            "user": user,
            "org_id": org_id,
        },
        "user_id": user_id,
    }


run = business_intelligence
