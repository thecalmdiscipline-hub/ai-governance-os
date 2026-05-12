from app.workflows.implementations.hr_recruitment import hr_recruitment


def test_hr_recruitment_returns_candidate_and_summary():
    result = hr_recruitment(
        {
            "input": {
                "candidate_name": "Jane Doe",
                "role": "Operations Manager",
            },
            "context": {},
            "user": "dennis_admin",
        },
        user_id=1,
        org_id=1,
    )

    assert result["status"] == "ok"
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["name"] == "Jane Doe"
    assert result["candidates"][0]["role"] == "Operations Manager"
    assert "summary" in result
