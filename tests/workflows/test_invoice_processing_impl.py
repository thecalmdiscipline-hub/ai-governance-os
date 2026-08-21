from app.workflows.implementations.invoice_processing import invoice_processing
from tests.conftest import mock_openai_response


def test_invoice_processing_extracts_amounts_and_invoice_number(monkeypatch):
    # The original fixture text ("Invoice 123 amount 500 EUR due 14 days") has
    # no describable product/service, so gpt-4o-mini correctly returned zero
    # line items — that was a stale test assertion, not a parsing bug (see
    # _parse_llm_response in app/workflows/implementations/invoice_processing.py,
    # which just counts whatever "line_items" the LLM returns). Mocking a
    # realistic LLM response makes the test deterministic and actually
    # exercises the line-item parsing path.
    mock_openai_response(monkeypatch, {
        "invoice_number": "123",
        "invoice_date": "2024-03-15",
        "vendor": {"name": "ACME BV", "address": "Teststraat 1, Amsterdam", "vat_number": "NL123456789B01"},
        "currency": "EUR",
        "line_items": [
            {"description": "Consulting services", "quantity": 1, "unit_price": 500.0, "line_total": 500.0}
        ],
        "subtotal": 500.0,
        "vat_rate": 0.0,
        "vat_amount": 0.0,
        "total_amount": 500.0,
        "anomalies": [],
        "summary": "Invoice 123 from ACME BV for consulting services, total 500 EUR.",
    })

    result = invoice_processing(
        {
            "input": {
                "invoice_text": "Invoice 123 amount 500 EUR due 14 days"
            },
            "context": {},
            "user": "dennis_admin",
        },
        user_id=1,
        org_id=1,
    )

    assert result["status"] == "ok"
    assert result["invoice_number"] == "123"
    assert result["currency"] == "EUR"
    assert result["line_item_count"] >= 1
    assert result["total_amount"] == 500.0
    assert "summary" in result
