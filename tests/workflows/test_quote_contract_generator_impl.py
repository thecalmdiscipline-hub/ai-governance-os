from app.workflows.services.runner import run_workflow

def test_quote_contract_generator_impl_returns_totals():
    payload = {
        "input": {
            "customer": {"name": "ACME", "email": "a@b.com", "company": "ACME BV"},
            "items": [
                {"description": "Service A", "qty": 2, "unit_price": 100},
                {"description": "Service B", "qty": 1, "unit_price": 50},
            ],
            "vat_rate": 0.21,
            "currency": "EUR",
            "payment_terms_days": 14,
            "valid_days": 14,
        },
        "context": {},
        "user": "dennis_admin",
    }

    out = run_workflow("quote_contract_generator", payload, user_id=1)
    assert out["status"] == "ok"
    assert out["workflow"] == "quote_contract_generator"
    assert "run_id" in out
    result = out["output"]
    assert result["status"] == "ok"
    assert result["currency"] == "EUR"
    assert result["subtotal"] == 250.0
    assert result["vat_amount"] == round(250.0 * 0.21, 2)
    assert result["total"] == round(250.0 + round(250.0 * 0.21, 2), 2)
    assert result["user_id"] == 1
