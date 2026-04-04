from app.workflows.implementations.customer_support import run

def test_customer_support_returns_ticket_id_and_triage():
    out = run(payload={"input": {"issue": "login_failed", "priority": "high"}, "context": {}, "user": "dennis_admin"}, user_id=1)
    assert out["ticket_id"].startswith("CS-")
    assert out["triage"]["issue"] == "login_failed"
    assert out["triage"]["priority"] == "high"
    assert out["user_id"] == 1
