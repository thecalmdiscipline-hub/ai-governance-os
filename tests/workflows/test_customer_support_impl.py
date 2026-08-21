from app.workflows.implementations.customer_support import run
from tests.conftest import mock_openai_response

def test_customer_support_returns_ticket_id_and_triage(monkeypatch):
    mock_openai_response(monkeypatch, {
        "priority": "high",
        "urgency_reason": "Login failures block users from accessing the product entirely.",
        "suggested_action": "Escalate to engineering for immediate investigation.",
        "summary": "Customer cannot log in, blocking product access.",
    })

    out = run(payload={"input": {"issue": "login_failed", "priority": "high"}, "context": {}, "user": "dennis_admin"}, user_id=1)
    assert out["ticket_id"].startswith("CS-")
    assert out["triage"]["issue"] == "login_failed"
    assert out["triage"]["priority"] == "high"
    assert out["user_id"] == 1
