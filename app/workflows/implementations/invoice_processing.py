"""
Invoice Processing workflow — LLM implementation.

Input fields:
  invoice_text       : Raw invoice text to analyse (required for useful output)

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  invoice_number     : Extracted invoice number
  invoice_date       : Invoice date as found in the document
  vendor             : {name, address, vat_number}
  currency           : Detected currency code (EUR, USD, GBP, …)
  line_items         : list[{description, quantity, unit_price, line_total}]
  line_item_count    : Number of line items
  detected_amounts   : list[float] — all monetary amounts found
  subtotal           : Sum before VAT
  vat_rate           : Detected VAT rate (e.g. 0.21 for 21%)
  vat_amount         : VAT amount
  total_amount       : Final total including VAT
  anomalies          : list[str] — missing fields or irregularities flagged
  summary            : Short narrative description of the invoice
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """You are an enterprise invoice processing AI. Extract all financial data accurately and in a structured format.

Analyse the provided invoice text and return a JSON extraction report.
Return valid JSON only — no prose, no markdown.

Required JSON schema:
{
  "invoice_number": "<invoice number or null if not found>",
  "invoice_date": "<date as written in the invoice, e.g. 2024-03-15, or null>",
  "vendor": {
    "name": "<supplier/vendor name or null>",
    "address": "<supplier address or null>",
    "vat_number": "<VAT/BTW/tax registration number or null>"
  },
  "currency": "<ISO 4217 code: EUR, USD, GBP, etc. — infer from symbols if needed>",
  "line_items": [
    {
      "description": "<product or service description>",
      "quantity": <number or 1 if not specified>,
      "unit_price": <float or null>,
      "line_total": <float — quantity × unit_price>
    }
  ],
  "subtotal": <float — sum of line totals before VAT, or best estimate>,
  "vat_rate": <float — e.g. 0.21 for 21%, or null if not determinable>,
  "vat_amount": <float or null>,
  "total_amount": <float — final amount including VAT, or best estimate>,
  "anomalies": ["<missing or inconsistent field 1>", "<issue 2>", ...],
  "summary": "<1-2 sentence description: vendor, what was purchased, total>"
}

Anomaly examples to flag:
- Missing invoice number, date, or vendor name
- VAT rate not stated or inconsistent with amounts
- Line item totals that do not sum to the subtotal
- Total amount inconsistent with subtotal + VAT
- Duplicate line items
- No line items found despite a stated total

If the input is empty or too short to extract meaningful data, set all fields to null and add an anomaly explaining this.
"""


def _build_user_message(invoice_text: str) -> str:
    text = invoice_text.strip()
    if not text:
        return "Invoice text: (empty — no content provided)"
    return f"Invoice text:\n\n{text[:8000]}"


def _parse_llm_response(content: str) -> Dict[str, Any]:
    data = json.loads(content)

    vendor_raw = data.get("vendor") or {}
    vendor = {
        "name": vendor_raw.get("name"),
        "address": vendor_raw.get("address"),
        "vat_number": vendor_raw.get("vat_number"),
    }

    line_items_raw = data.get("line_items") or []
    if not isinstance(line_items_raw, list):
        line_items_raw = []

    line_items: List[Dict[str, Any]] = []
    detected_amounts: List[float] = []

    for item in line_items_raw:
        if not isinstance(item, dict):
            continue
        try:
            qty = float(item.get("quantity") or 1)
            unit_price = float(item.get("unit_price") or 0)
            line_total_raw = item.get("line_total")
            line_total = float(line_total_raw) if line_total_raw is not None else round(qty * unit_price, 2)
        except (TypeError, ValueError):
            continue
        line_items.append({
            "description": str(item.get("description") or ""),
            "quantity": qty,
            "unit_price": unit_price,
            "line_total": line_total,
        })
        if line_total > 0:
            detected_amounts.append(line_total)

    def _safe_float(val: Any) -> Optional[float]:
        try:
            return round(float(val), 2) if val is not None else None
        except (TypeError, ValueError):
            return None

    subtotal = _safe_float(data.get("subtotal"))
    vat_rate = _safe_float(data.get("vat_rate"))
    vat_amount = _safe_float(data.get("vat_amount"))
    total_amount = _safe_float(data.get("total_amount"))

    if subtotal is not None and subtotal > 0 and subtotal not in detected_amounts:
        detected_amounts.append(subtotal)
    if total_amount is not None and total_amount > 0 and total_amount not in detected_amounts:
        detected_amounts.append(total_amount)

    anomalies = data.get("anomalies") or []
    if not isinstance(anomalies, list):
        anomalies = []

    currency = str(data.get("currency") or "UNKNOWN").upper()

    return {
        "invoice_number": data.get("invoice_number"),
        "invoice_date": data.get("invoice_date"),
        "vendor": vendor,
        "currency": currency,
        "line_items": line_items,
        "line_item_count": len(line_items),
        "detected_amounts": sorted(set(detected_amounts)),
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total_amount": total_amount,
        "anomalies": [str(a) for a in anomalies],
        "summary": str(data.get("summary") or ""),
    }


def _fallback_result(invoice_text: str, reason: str) -> Dict[str, Any]:
    return {
        "invoice_number": None,
        "invoice_date": None,
        "vendor": {"name": None, "address": None, "vat_number": None},
        "currency": "UNKNOWN",
        "line_items": [],
        "line_item_count": 0,
        "detected_amounts": [],
        "subtotal": None,
        "vat_rate": None,
        "vat_amount": None,
        "total_amount": None,
        "anomalies": [f"Automated extraction unavailable: {reason}"],
        "summary": f"Invoice could not be automatically processed: {reason}",
    }


def invoice_processing(
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    input_data = payload.get("input", {}) or {}
    invoice_text = str(input_data.get("invoice_text") or "")
    context = payload.get("context", {}) or {}
    user = payload.get("user")

    received = {
        "input": input_data,
        "context": context,
        "user": user,
        "org_id": org_id,
    }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("invoice_processing: OPENAI_API_KEY not set — returning degraded response")
        return {
            "status": "degraded",
            **_fallback_result(invoice_text, "OPENAI_API_KEY not configured"),
            "degraded_reason": "OPENAI_API_KEY not configured",
            "received": received,
            "user_id": user_id,
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(invoice_text)

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=1500,
        )

        raw_content = response.choices[0].message.content or ""
        result = _parse_llm_response(raw_content)

        logger.info(
            "invoice_processing: LLM call succeeded — invoice=%s total=%s %s anomalies=%d",
            result["invoice_number"],
            result["total_amount"],
            result["currency"],
            len(result["anomalies"]),
        )

        return {
            "status": "ok",
            **result,
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,
            "received": received,
            "user_id": user_id,
        }

    except openai.RateLimitError:
        logger.warning("invoice_processing: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("invoice_processing: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("invoice_processing: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("invoice_processing: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("invoice_processing: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    return {
        "status": "degraded",
        **_fallback_result(invoice_text, reason),
        "degraded_reason": reason,
        "received": received,
        "user_id": user_id,
    }


run = invoice_processing
