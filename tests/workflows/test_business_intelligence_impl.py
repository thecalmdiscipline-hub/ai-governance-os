from app.workflows.implementations.business_intelligence import business_intelligence
from tests.conftest import mock_openai_response


def test_business_intelligence_returns_insights(monkeypatch):
    mock_openai_response(monkeypatch, {
        "focus_area": "sales",
        "summary": "Sales performance is trending positively this quarter with strong pipeline coverage.",
        "kpis": ["Win rate", "Average deal size", "Sales cycle length"],
        "recommendations": ["Focus on top-of-funnel lead quality", "Shorten follow-up cadence"],
        "priority_level": "medium",
        "action_items": ["Review pipeline with sales team"],
        "risks": ["Pipeline concentration in few large deals"],
    })

    result = business_intelligence(
        {
            "input": {
                "question": "Show latest business insights for sales performance"
            },
            "context": {},
            "user": "dennis_admin",
        },
        user_id=1,
        org_id=1,
    )

    assert result["status"] == "ok"
    assert "insights" in result
    assert result["insights"]["focus_area"] == "sales"
    assert len(result["insights"]["recommendations"]) >= 1
    assert "summary" in result
