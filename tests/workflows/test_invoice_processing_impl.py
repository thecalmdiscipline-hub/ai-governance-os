from app.workflows.implementations.invoice_processing import invoice_processing


def test_invoice_processing_extracts_amounts_and_invoice_number():
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
