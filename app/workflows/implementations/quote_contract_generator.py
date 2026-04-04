from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

def quote_contract_generator(payload: Dict[str, Any], user_id: int | None = None) -> Dict[str, Any]:
    inp = (payload or {}).get("input", {}) or {}
    context = (payload or {}).get("context", {}) or {}
    user = (payload or {}).get("user")

    customer = inp.get("customer") or {}
    items = inp.get("items") or []
    currency = inp.get("currency") or "EUR"

    subtotal = 0.0
    norm_items = []
    for it in items:
        desc = it.get("description") if isinstance(it, dict) else None
        qty = float((it.get("qty") if isinstance(it, dict) else 1) or 1)
        unit_price = float((it.get("unit_price") if isinstance(it, dict) else 0) or 0)
        line_total = qty * unit_price
        subtotal += line_total
        norm_items.append(
            {
                "description": desc or "item",
                "qty": qty,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    vat_rate = float(inp.get("vat_rate") or 0)
    vat_amount = round(subtotal * vat_rate, 2)
    total = round(subtotal + vat_amount, 2)

    quote_id = f"Q-{uuid4().hex[:10].upper()}"
    contract_id = f"C-{uuid4().hex[:10].upper()}"

    return {
        "quote_id": quote_id,
        "contract_id": contract_id,
        "status": "ok",
        "currency": currency,
        "customer": {
            "name": customer.get("name"),
            "email": customer.get("email"),
            "company": customer.get("company"),
        },
        "items": norm_items,
        "subtotal": round(subtotal, 2),
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
        "terms": {
            "payment_terms_days": int(inp.get("payment_terms_days") or 14),
            "valid_days": int(inp.get("valid_days") or 14),
        },
        "received": {"input": inp, "context": context, "user": user},
        "user_id": user_id,
    }
