from app.workflows.services.runner import run_workflow


def test_meeting_agenda_assistant_impl_returns_agenda():
    payload = {
        "input": {
            "title": "Weekly Sync",
            "duration_min": 45,
            "participants": ["a@b.com", "c@d.com"],
            "goals": ["Status update", "Blockers", "Next steps"],
        },
        "context": {},
        "user": "dennis_admin",
    }

    out = run_workflow("meeting_agenda_assistant", payload, user_id=1)
    assert out["status"] == "ok"
    assert out["workflow"] == "meeting_agenda_assistant"
    assert "run_id" in out

    result = out["output"]
    assert result["status"] == "ok"
    assert result["title"] == "Weekly Sync"
    assert result["duration_min"] == 45
    assert isinstance(result["agenda"], list)
    assert len(result["agenda"]) >= 2
    assert result["user_id"] == 1
