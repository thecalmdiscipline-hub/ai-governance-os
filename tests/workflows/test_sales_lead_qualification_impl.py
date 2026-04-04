from app.workflows.implementations.sales_lead_qualification import sales_lead_qualification_run


def test_sales_lead_qualification_impl_basic():
    payload = {"input": {"lead": {"email": "a@b.com", "company": "ACME"}, "source": "inbound"}, "context": {}, "user": "dennis_admin"}
    out = sales_lead_qualification_run(payload, user_id=1)
    assert out["workflow"] == "sales_lead_qualification"
    assert out["status"] == "ok"
    assert out["qualification"] in {"low", "medium", "high"}
    assert isinstance(out["score"], int)
    assert out["user_id"] == 1
