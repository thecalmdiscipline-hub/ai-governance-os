from app.workflows.implementations.business_intelligence import business_intelligence


def test_business_intelligence_returns_insights():
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
