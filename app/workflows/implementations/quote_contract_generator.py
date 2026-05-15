"""
Quote & Contract Generator workflow — LLM implementation.

Input fields (all optional):
  customer           : {name, email, company, address}
  items              : list[{description, qty, unit_price}]
  currency           : ISO currency code (default EUR)
  vat_rate           : VAT rate as decimal (e.g. 0.21 for 21%)
  payment_terms_days : Payment due in N days (default 14)
  valid_days         : Quote validity in days (default 14)
  project_description: Overall project or service description
  scope              : Scope of work / deliverables
  special_requirements: Any special client requirements

Output (always returned, even on LLM failure):
  status             : "ok" | "degraded"
  quote_id           : Unique quote reference (Q-xxxx)
  contract_id        : Unique contract reference (C-xxxx)
  currency           : Currency code
  customer           : {name, email, company, address}
  items              : list[{description, qty, unit_price, line_total}]
  subtotal           : Pre-VAT total (calculated in code, not by LLM)
  vat_rate           : VAT rate
  vat_amount         : VAT amount
  total              : Final total including VAT
  terms              : {payment_terms_days, valid_days}
  quote_text         : AI-generated professional Dutch quote introduction
  scope_description  : Narrative description of the full scope
  contract_terms     : list[str] — contract conditions
  payment_note       : Professional payment terms formulation
  validity_note      : Professional validity period statement
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = """Je bent een enterprise quote en contract AI voor B2B dienstverleners. Genereer professionele, juridisch correcte offertes en contracten in het Nederlands.

Analyseer de opdracht en genereer een gestructureerd JSON-document met offerte- en contractteksten.
Retourneer alleen geldige JSON — geen proza, geen markdown.

Vereist JSON-schema:
{
  "quote_text": "<professionele Nederlandse inleiding van de offerte, 2-3 alinea's, inclusief aanleiding, aanpak en meerwaarde>",
  "scope_description": "<beknopte Nederlandse omschrijving van de volledige opdracht en deliverables, 1-2 alinea's>",
  "enhanced_items": [
    {
      "original_description": "<originele beschrijving zoals aangeleverd>",
      "professional_description": "<professionele Nederlandse formulering van dit regelitem>"
    }
  ],
  "contract_terms": [
    "<contractvoorwaarde 1, volledig uitgeschreven in professioneel Nederlands>",
    "<contractvoorwaarde 2>",
    ...
  ],
  "payment_note": "<professionele Nederlandse formulering van de betalingsvoorwaarden>",
  "validity_note": "<professionele Nederlandse formulering van de geldigheidsduur van de offerte>",
  "special_conditions": ["<eventuele bijzondere voorwaarde>"]
}

Richtlijnen voor contract_terms (lever minimaal 6 standaard B2B-voorwaarden):
- Betalingstermijn en gevolgen van te late betaling
- Intellectueel eigendom en overdracht van rechten
- Aansprakelijkheidsbeperking
- Vertrouwelijkheid / geheimhouding
- Opzegtermijn en annuleringskosten
- Toepasselijk recht (Nederland) en bevoegde rechter

Schrijf in formeel maar toegankelijk zakelijk Nederlands.
Pas de offerte-tekst aan op de klant, het product en de context.
Als er geen klantgegevens beschikbaar zijn, schrijf dan in algemene termen.
"""


def _normalise_items(raw_items: Any) -> tuple[List[Dict[str, Any]], float]:
    """Compute line items and subtotal deterministically in code."""
    if not isinstance(raw_items, list):
        raw_items = []
    items: List[Dict[str, Any]] = []
    subtotal = 0.0
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        try:
            qty = float(it.get("qty") or 1)
            unit_price = float(it.get("unit_price") or 0)
        except (TypeError, ValueError):
            qty, unit_price = 1.0, 0.0
        line_total = round(qty * unit_price, 2)
        subtotal += line_total
        items.append({
            "description": str(it.get("description") or "item"),
            "qty": qty,
            "unit_price": unit_price,
            "line_total": line_total,
        })
    return items, round(subtotal, 2)


def _build_user_message(inp: Dict[str, Any], items: List[Dict], subtotal: float, total: float) -> str:
    customer = inp.get("customer") or {}
    parts: List[str] = ["Offerte-aanvraag:"]

    customer_fields = [
        ("Klant", customer.get("name")),
        ("Bedrijf", customer.get("company")),
        ("E-mail", customer.get("email")),
        ("Adres", customer.get("address")),
    ]
    for label, value in customer_fields:
        if value:
            parts.append(f"  {label}: {value}")

    project_description = str(inp.get("project_description") or "").strip()
    if project_description:
        parts.append(f"\nOpdracht:\n{project_description[:2000]}")

    scope = str(inp.get("scope") or "").strip()
    if scope:
        parts.append(f"\nScope / deliverables:\n{scope[:1500]}")

    special = str(inp.get("special_requirements") or "").strip()
    if special:
        parts.append(f"\nBijzondere vereisten:\n{special[:500]}")

    currency = str(inp.get("currency") or "EUR").upper()
    vat_rate = float(inp.get("vat_rate") or 0)
    payment_days = int(inp.get("payment_terms_days") or 14)
    valid_days = int(inp.get("valid_days") or 14)

    parts.append(f"\nRegelitems ({currency}):")
    for item in items:
        parts.append(f"  - {item['description']}: {item['qty']} × {item['unit_price']} = {item['line_total']}")

    parts.append(
        f"\nFinancieel: subtotaal {subtotal} {currency}, BTW {int(vat_rate * 100)}%, "
        f"totaal {total} {currency}"
    )
    parts.append(f"Betalingstermijn: {payment_days} dagen")
    parts.append(f"Geldigheid offerte: {valid_days} dagen")

    return "\n".join(parts)


def _apply_enhanced_descriptions(items: List[Dict], enhanced: List[Dict]) -> List[Dict]:
    """Replace item descriptions with AI-enhanced versions where available."""
    enhanced_map = {
        str(e.get("original_description") or "").strip(): str(e.get("professional_description") or "")
        for e in enhanced
        if isinstance(e, dict)
    }
    result = []
    for item in items:
        orig = item["description"].strip()
        result.append({**item, "description": enhanced_map.get(orig) or orig})
    return result


def _parse_llm_response(content: str, items: List[Dict]) -> Dict[str, Any]:
    data = json.loads(content)

    def _as_str_list(val: Any) -> List[str]:
        if not isinstance(val, list):
            return []
        return [str(v) for v in val if v]

    enhanced_raw = data.get("enhanced_items") or []
    enhanced_items = _apply_enhanced_descriptions(items, enhanced_raw if isinstance(enhanced_raw, list) else [])

    return {
        "items": enhanced_items,
        "quote_text": str(data.get("quote_text") or ""),
        "scope_description": str(data.get("scope_description") or ""),
        "contract_terms": _as_str_list(data.get("contract_terms")),
        "payment_note": str(data.get("payment_note") or ""),
        "validity_note": str(data.get("validity_note") or ""),
        "special_conditions": _as_str_list(data.get("special_conditions")),
    }


def _fallback_text(reason: str) -> Dict[str, Any]:
    return {
        "quote_text": f"Offerte kon niet automatisch worden gegenereerd: {reason}",
        "scope_description": "",
        "contract_terms": [
            "Betalingstermijn: conform de overeengekomen termijn op de offerte.",
            "Toepasselijk recht: Nederlands recht.",
        ],
        "payment_note": "",
        "validity_note": "",
        "special_conditions": [],
    }


def quote_contract_generator(
    payload: Dict[str, Any],
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
) -> Dict[str, Any]:
    inp = (payload or {}).get("input", {}) or {}
    context = (payload or {}).get("context", {}) or {}
    user = (payload or {}).get("user")

    customer_raw = inp.get("customer") or {}
    customer = {
        "name": customer_raw.get("name"),
        "email": customer_raw.get("email"),
        "company": customer_raw.get("company"),
        "address": customer_raw.get("address"),
    }

    currency = str(inp.get("currency") or "EUR").upper()
    vat_rate = float(inp.get("vat_rate") or 0)
    payment_terms_days = int(inp.get("payment_terms_days") or 14)
    valid_days = int(inp.get("valid_days") or 14)

    # Financial calculations always done in code — never delegated to LLM
    items, subtotal = _normalise_items(inp.get("items"))
    vat_amount = round(subtotal * vat_rate, 2)
    total = round(subtotal + vat_amount, 2)
    valid_until = (date.today() + timedelta(days=valid_days)).isoformat()

    quote_id = f"Q-{uuid4().hex[:10].upper()}"
    contract_id = f"C-{uuid4().hex[:10].upper()}"

    base_output = {
        "quote_id": quote_id,
        "contract_id": contract_id,
        "currency": currency,
        "customer": customer,
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
        "terms": {
            "payment_terms_days": payment_terms_days,
            "valid_days": valid_days,
            "valid_until": valid_until,
        },
        "user_id": user_id,
    }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("quote_contract_generator: OPENAI_API_KEY not set — returning degraded response")
        return {
            "status": "degraded",
            **base_output,
            "items": items,
            **_fallback_text("OPENAI_API_KEY not configured"),
            "degraded_reason": "OPENAI_API_KEY not configured",
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(inp, items, subtotal, total)

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        raw_content = response.choices[0].message.content or ""
        parsed = _parse_llm_response(raw_content, items)

        logger.info(
            "quote_contract_generator: LLM call succeeded — quote=%s total=%s %s terms=%d",
            quote_id,
            total,
            currency,
            len(parsed["contract_terms"]),
        )

        return {
            "status": "ok",
            **base_output,
            **parsed,
            "model": _MODEL,
            "tokens_used": response.usage.total_tokens if response.usage else None,
        }

    except openai.RateLimitError:
        logger.warning("quote_contract_generator: OpenAI rate limit reached")
        reason = "OpenAI rate limit reached — retry later"

    except openai.APIConnectionError as exc:
        logger.warning("quote_contract_generator: OpenAI connection error: %s", exc)
        reason = f"Could not reach OpenAI API: {exc}"

    except openai.APIStatusError as exc:
        logger.warning("quote_contract_generator: OpenAI API error %s: %s", exc.status_code, exc.message)
        reason = f"OpenAI API error {exc.status_code}"

    except json.JSONDecodeError as exc:
        logger.error("quote_contract_generator: Failed to parse LLM JSON response: %s", exc)
        reason = "LLM returned unparseable response"

    except Exception as exc:
        logger.error("quote_contract_generator: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    return {
        "status": "degraded",
        **base_output,
        "items": items,
        **_fallback_text(reason),
        "degraded_reason": reason,
    }


run = quote_contract_generator
