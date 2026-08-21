from app.workflows.implementations.sales_lead_qualification import run


def test_sales_lead_qualification_impl_basic():
    payload = {"input": {"lead": {"email": "a@b.com", "company": "ACME"}, "source": "inbound"}, "context": {}, "user": "dennis_admin"}
    out = run(payload, user_id=1)
    assert out["workflow"] == "sales_lead_qualification"
    assert out["status"] == "ok"
    # _qualify() only ever returns one of these three labels — see
    # app/workflows/implementations/sales_lead_qualification.py:142-147
    assert out["qualification"] in {"qualified", "needs_nurturing", "unqualified"}
    assert isinstance(out["score"], int)
    assert out["user_id"] == 1
