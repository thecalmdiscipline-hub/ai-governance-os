from __future__ import annotations
from typing import Any, Dict, Optional

def invoice_processing(payload: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    inp = (payload or {}).get("input", {})
    invoices = inp.get("invoices", [])

    total = sum(float(i.get("amount",0)) for i in invoices if isinstance(i, dict))

    return {
        "status": "ok",
        "count": len(invoices),
        "total_amount": total,
        "received": payload,
        "user_id": user_id,
    }
