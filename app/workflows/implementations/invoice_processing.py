import re
from typing import Any, Dict, List, Optional


def _extract_amounts(text: str) -> List[float]:
    normalized = text.replace(",", ".")
    matches = re.findall(r'(?<!\d)(\d+(?:\.\d{1,2})?)(?!\d)', normalized)
    amounts: List[float] = []

    for raw in matches:
        try:
            value = float(raw)
            if value > 0:
                amounts.append(value)
        except ValueError:
            continue

    return amounts


def _extract_invoice_number(text: str) -> Optional[str]:
    patterns = [
        r'invoice[\s#:;-]*([A-Za-z0-9\-\/]+)',
        r'factuur[\s#:;-]*([A-Za-z0-9\-\/]+)',
        r'inv[\s#:;-]*([A-Za-z0-9\-\/]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _extract_currency(text: str) -> str:
    upper = text.upper()

    if "EUR" in upper or "€" in text:
        return "EUR"
    if "USD" in upper or "$" in text:
        return "USD"
    if "GBP" in upper or "£" in text:
        return "GBP"

    return "UNKNOWN"


def invoice_processing(payload: Dict[str, Any], user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    invoice_text = str(input_data.get("invoice_text", "") or "")
    context = payload.get("context", {}) or {}
    user = payload.get("user")

    amounts = _extract_amounts(invoice_text)
    invoice_number = _extract_invoice_number(invoice_text)
    currency = _extract_currency(invoice_text)

    subtotal = max(amounts) if amounts else 0.0
    line_item_count = len(amounts)

    summary = (
        f"Processed invoice text"
        f"{f' for invoice {invoice_number}' if invoice_number else ''}. "
        f"Detected {line_item_count} numeric value(s) and estimated total {subtotal:.2f} {currency}."
    )

    return {
        "status": "ok",
        "invoice_number": invoice_number,
        "currency": currency,
        "line_item_count": line_item_count,
        "detected_amounts": amounts,
        "subtotal": round(subtotal, 2),
        "total_amount": round(subtotal, 2),
        "summary": summary,
        "received": {
            "input": input_data,
            "context": context,
            "user": user,
            "org_id": org_id,
        },
        "user_id": user_id,
    }


run = invoice_processing
