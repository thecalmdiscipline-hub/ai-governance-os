"""
Quote & Contract Generator workflow — LLM implementation.

Input fields (all optional):
  customer           : {name, email, company, address}
  items              : list[{description, qty, unit_price}]
  currency            : ISO currency code (default EUR)
  vat_rate            : VAT rate as decimal (e.g. 0.21 for 21%)
  payment_terms_days  : Payment due in N days (default 14)
  valid_days          : Quote validity in days (default 14)
  project_description : Overall project or service description
  scope               : Scope of work / deliverables
  special_requirements: Any special client requirements
  output_language     : "nl" (default) or "en" — the language of the
                         AI-generated narrative text (quote_text,
                         scope_description, contract_terms, payment_note,
                         validity_note, special_conditions, and the
                         enhanced item descriptions). Omitted, empty, or
                         "nl" is identical to this workflow's behaviour
                         before this field existed — Dutch, unchanged. Any
                         value other than "nl"/"en" (case-insensitive) is
                         rejected with HTTP 422 by the router before this
                         function is even called — see
                         app/workflows/routers/quote_contract_generator.py.

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
  output_language    : the language actually used ("nl" or "en")
  quote_text         : AI-generated professional quote introduction, in output_language
  scope_description  : Narrative description of the full scope, in output_language
  contract_terms     : list[str] — contract conditions, in output_language
  payment_note       : Professional payment terms formulation, in output_language
  validity_note      : Professional validity period statement, in output_language

PII handling: the narrative fields above are generated from an anonymised
version of the request (see app.core.pii_anonymizer) so that no personal
data reaches OpenAI. Unlike every other workflow, this one hands the LLM's
own free-text response back to the client — so before returning, any
anonymization placeholder left in that text (e.g. an address that was
anonymized before the call) is restored to its real value via
pii_anonymizer.restore_placeholders(). This is safe: it only reveals the
client's own data back into the same request that supplied it in the first
place, nothing is exposed to a new party. Any placeholder the restore step
cannot resolve (e.g. one the LLM paraphrased or invented) is never shown
raw — see restore_placeholders() for the fallback. Found and fixed
2026-10-05 after a real demo run showed a literal "<LOCATIE>" token in the
generated quote text — see CLAUDE.md §6.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core import pii_anonymizer

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

SUPPORTED_OUTPUT_LANGUAGES = ("nl", "en")


def resolve_output_language(value: Any) -> Optional[str]:
    """Normalises an `output_language` input value.

    Returns:
        "nl" for a missing/empty value (the pre-existing default, Dutch,
        unchanged behaviour); the normalised code ("nl"/"en", lower-cased
        and trimmed) for a supported value; or None if a value is present
        but not one of SUPPORTED_OUTPUT_LANGUAGES.

    Callers MUST treat None as a validation error. The router returns HTTP
    422 for it (see app/workflows/routers/quote_contract_generator.py);
    this function itself only normalises/validates, it never raises or
    responds, so it can be unit-tested and reused from both the router and
    this module without pulling in FastAPI.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return "nl"
    lang = str(value).strip().lower()
    return lang if lang in SUPPORTED_OUTPUT_LANGUAGES else None


# Dutch system prompt — byte-identical to this workflow's original, only
# system prompt before output_language existed. Selected whenever
# output_language resolves to "nl" (the default).
_SYSTEM_PROMPT_NL = """Je bent een enterprise quote en contract AI voor B2B dienstverleners. Genereer professionele, juridisch correcte offertes en contracten in het Nederlands.

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

# English system prompt (added 2026-10-05 for output_language="en"). A
# faithful translation of the Dutch prompt above, with one deliberate
# adaptation: the governing-law contract term no longer hardcodes
# "Netherlands" (that would just reproduce the same category of
# language/content mismatch this feature exists to fix) — it instead asks
# the model to use the client's own context, or state it generically.
_SYSTEM_PROMPT_EN = """You are an enterprise quote and contract AI for B2B service providers. Generate professional, legally sound quotes and contracts in English.

Analyse the assignment and generate a structured JSON document with quote and contract text.
Return only valid JSON — no prose, no markdown.

Required JSON schema:
{
  "quote_text": "<professional English introduction to the quote, 2-3 paragraphs, including context, approach and value proposition>",
  "scope_description": "<concise English description of the full assignment and deliverables, 1-2 paragraphs>",
  "enhanced_items": [
    {
      "original_description": "<original description as supplied>",
      "professional_description": "<professional English formulation of this line item>"
    }
  ],
  "contract_terms": [
    "<contract term 1, fully written out in professional English>",
    "<contract term 2>",
    ...
  ],
  "payment_note": "<professional English formulation of the payment terms>",
  "validity_note": "<professional English formulation of the quote's validity period>",
  "special_conditions": ["<any special condition>"]
}

Guidelines for contract_terms (provide at least 6 standard B2B terms):
- Payment term and consequences of late payment
- Intellectual property and transfer of rights
- Limitation of liability
- Confidentiality / non-disclosure
- Notice period and cancellation fees
- Governing law and competent jurisdiction (use the client's own context if it implies one; otherwise state this generically without presuming a specific country)

Write in formal but accessible business English.
Adapt the quote text to the client, the product and the context.
If no client details are available, write in general terms.
"""

_SYSTEM_PROMPTS: Dict[str, str] = {"nl": _SYSTEM_PROMPT_NL, "en": _SYSTEM_PROMPT_EN}

# Labels for _build_user_message() below, per output_language. The "nl"
# column is exactly what the original (pre-output_language) implementation
# hardcoded, so output_language omitted/"nl" produces byte-identical user
# messages to before this field existed.
_USER_MESSAGE_LABELS: Dict[str, Dict[str, str]] = {
    "nl": {
        "header": "Offerte-aanvraag:",
        "customer": "Klant",
        "company": "Bedrijf",
        "email": "E-mail",
        "address": "Adres",
        "assignment": "Opdracht:",
        "scope": "Scope / deliverables:",
        "special": "Bijzondere vereisten:",
        "line_items": "Regelitems",
        "financial": "Financieel: subtotaal {subtotal} {currency}, BTW {vat_pct}%, totaal {total} {currency}",
        "payment_term": "Betalingstermijn: {days} dagen",
        "validity": "Geldigheid offerte: {days} dagen",
    },
    "en": {
        "header": "Quote request:",
        "customer": "Customer",
        "company": "Company",
        "email": "Email",
        "address": "Address",
        "assignment": "Assignment:",
        "scope": "Scope / deliverables:",
        "special": "Special requirements:",
        "line_items": "Line items",
        "financial": "Financials: subtotal {subtotal} {currency}, VAT {vat_pct}%, total {total} {currency}",
        "payment_term": "Payment term: {days} days",
        "validity": "Quote validity: {days} days",
    },
}


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


def _build_user_message(
    inp: Dict[str, Any], items: List[Dict], subtotal: float, total: float, output_language: str
) -> str:
    labels = _USER_MESSAGE_LABELS[output_language]
    customer = inp.get("customer") or {}
    parts: List[str] = [labels["header"]]

    customer_fields = [
        (labels["customer"], customer.get("name")),
        (labels["company"], customer.get("company")),
        (labels["email"], customer.get("email")),
        (labels["address"], customer.get("address")),
    ]
    for label, value in customer_fields:
        if value:
            parts.append(f"  {label}: {value}")

    project_description = str(inp.get("project_description") or "").strip()
    if project_description:
        parts.append(f"\n{labels['assignment']}\n{project_description[:2000]}")

    scope = str(inp.get("scope") or "").strip()
    if scope:
        parts.append(f"\n{labels['scope']}\n{scope[:1500]}")

    special = str(inp.get("special_requirements") or "").strip()
    if special:
        parts.append(f"\n{labels['special']}\n{special[:500]}")

    currency = str(inp.get("currency") or "EUR").upper()
    vat_rate = float(inp.get("vat_rate") or 0)
    payment_days = int(inp.get("payment_terms_days") or 14)
    valid_days = int(inp.get("valid_days") or 14)

    parts.append(f"\n{labels['line_items']} ({currency}):")
    for item in items:
        parts.append(f"  - {item['description']}: {item['qty']} × {item['unit_price']} = {item['line_total']}")

    parts.append(
        "\n"
        + labels["financial"].format(
            subtotal=subtotal, currency=currency, vat_pct=int(vat_rate * 100), total=total
        )
    )
    parts.append(labels["payment_term"].format(days=payment_days))
    parts.append(labels["validity"].format(days=valid_days))

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


def _restore_pii_in_parsed_response(parsed: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Restores anonymization placeholders in every LLM-generated text
    field of `parsed`, using the mapping from this one request's
    anonymize_text_with_mapping() call (see the module docstring for why
    this is safe). Covers every free-text field the LLM can populate,
    including the per-item "professional_description" — not just
    quote_text/contract_terms — since any of them could echo anonymized
    input back.
    """
    restore = pii_anonymizer.restore_placeholders
    parsed = dict(parsed)
    parsed["quote_text"] = restore(parsed.get("quote_text", ""), mapping)
    parsed["scope_description"] = restore(parsed.get("scope_description", ""), mapping)
    parsed["payment_note"] = restore(parsed.get("payment_note", ""), mapping)
    parsed["validity_note"] = restore(parsed.get("validity_note", ""), mapping)
    parsed["contract_terms"] = [restore(t, mapping) for t in parsed.get("contract_terms", [])]
    parsed["special_conditions"] = [restore(t, mapping) for t in parsed.get("special_conditions", [])]
    parsed["items"] = [
        {**item, "description": restore(item.get("description", ""), mapping)}
        for item in parsed.get("items", [])
    ]
    return parsed


def _fallback_text(reason: str, output_language: str) -> Dict[str, Any]:
    if output_language == "en":
        return {
            "quote_text": f"The quote could not be generated automatically: {reason}",
            "scope_description": "",
            "contract_terms": [
                "Payment term: as agreed on the quote.",
                "Governing law: as applicable to the parties.",
            ],
            "payment_note": "",
            "validity_note": "",
            "special_conditions": [],
        }
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

    # output_language should already have been validated to "nl"/"en" by
    # the router (HTTP 422 otherwise) — but this function may also be
    # called directly (tests, scripts, a future caller that bypasses the
    # router), so it still fails safe here rather than assuming.
    output_language = resolve_output_language(inp.get("output_language"))

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

    if output_language is None:
        logger.warning(
            "quote_contract_generator: invalid output_language %r — returning degraded response",
            inp.get("output_language"),
        )
        fallback_language = "nl"
        return {
            "status": "degraded",
            **base_output,
            "items": items,
            "output_language": fallback_language,
            **_fallback_text(
                f"invalid output_language (allowed: {', '.join(SUPPORTED_OUTPUT_LANGUAGES)})",
                fallback_language,
            ),
            "degraded_reason": f"invalid output_language (allowed: {', '.join(SUPPORTED_OUTPUT_LANGUAGES)})",
        }

    base_output["output_language"] = output_language

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("quote_contract_generator: OPENAI_API_KEY not set — returning degraded response")
        return {
            "status": "degraded",
            **base_output,
            "items": items,
            **_fallback_text("OPENAI_API_KEY not configured", output_language),
            "degraded_reason": "OPENAI_API_KEY not configured",
        }

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        user_message = _build_user_message(inp, items, subtotal, total, output_language)
        user_message, pii_mapping = pii_anonymizer.anonymize_text_with_mapping(
            user_message, workflow="quote_contract_generator"
        )

        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPTS[output_language]},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        raw_content = response.choices[0].message.content or ""
        parsed = _parse_llm_response(raw_content, items)
        parsed = _restore_pii_in_parsed_response(parsed, pii_mapping)

        logger.info(
            "quote_contract_generator: LLM call succeeded — quote=%s total=%s %s terms=%d lang=%s",
            quote_id,
            total,
            currency,
            len(parsed["contract_terms"]),
            output_language,
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

    except pii_anonymizer.PIIAnonymizerUnavailable as exc:
        logger.error("quote_contract_generator: PII-anonimisering mislukt — LLM-call geblokkeerd: %s", exc)
        reason = str(exc)

    except Exception as exc:
        logger.error("quote_contract_generator: Unexpected error: %s", exc, exc_info=True)
        reason = f"Unexpected error: {type(exc).__name__}"

    return {
        "status": "degraded",
        **base_output,
        "items": items,
        **_fallback_text(reason, output_language),
        "degraded_reason": reason,
    }


run = quote_contract_generator
