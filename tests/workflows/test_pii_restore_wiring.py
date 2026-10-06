"""Batch J (2026-10-06): verifies that every workflow besides Quote &
Contract Generator (which already has its own dedicated test, see
tests/workflows/test_quote_contract_generator_impl.py and
test_quote_contract_generator_output_language.py) actually restores
anonymization placeholders in its LLM-generated free-text output fields.

This does not re-test Presidio's detection or restore_placeholders()'s own
correctness — that is exhaustively covered, workflow-independently, by
tests/test_pii_anonymizer.py. It tests the WIRING: that each workflow (a)
calls anonymize_text_with_mapping() and keeps the resulting mapping, and
(b) runs the specific output field(s) that can carry the LLM's own free
text through restore_placeholders() before returning them — so a known
placeholder in the mapping comes back as its real value, and a
placeholder-shaped token NOT in the mapping (e.g. one the LLM invented or
mangled) is never shown raw, only as the neutral "[omitted]" filler.

Each test fixes anonymize_text_with_mapping() to return a known mapping
regardless of the actual message text (decoupling this test from each
workflow's own message-building logic, already covered elsewhere), and
mocks the OpenAI response so the field under test contains the mapped
placeholder plus one unmapped, placeholder-shaped token.
"""
from __future__ import annotations

from app.core import pii_anonymizer
from tests.conftest import mock_openai_response

_MAPPING = {"<LOCATIE>": "Sheffield"}
_PLACEHOLDER = "<LOCATIE>"
_UNMAPPED_PLACEHOLDER = "<ONBEKEND>"  # placeholder-shaped, deliberately not in _MAPPING


def _fixed_mapping_anonymize(monkeypatch):
    """Patches anonymize_text_with_mapping() to always return _MAPPING,
    regardless of the actual input text — the message-building logic
    itself is covered by the existing per-workflow _impl tests."""

    def _fake(text, workflow=None):
        return text, dict(_MAPPING)

    monkeypatch.setattr(pii_anonymizer, "anonymize_text_with_mapping", _fake)


def test_sales_lead_qualification_restores_summary_and_list_fields(monkeypatch):
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "score": 70,
        "qualification": "needs_nurturing",
        "summary": f"Lead is based in {_PLACEHOLDER} and seems promising.",
        "strengths": [f"Strong presence in {_PLACEHOLDER}", f"Also noted {_UNMAPPED_PLACEHOLDER}"],
        "weaknesses": [],
        "next_actions": [],
    })

    from app.workflows.implementations.sales_lead_qualification import run

    result = run({"input": {"lead": {"company": "ACME"}}}, user_id=1)

    assert result["status"] == "ok"
    assert result["summary"] == "Lead is based in Sheffield and seems promising."
    assert result["strengths"][0] == "Strong presence in Sheffield"
    assert result["strengths"][1] == "Also noted [omitted]"
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_customer_support_restores_triage_free_text(monkeypatch):
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "priority": "high",
        "urgency_reason": f"Customer is located in {_UNMAPPED_PLACEHOLDER}.",
        "suggested_action": f"Escalate to the {_PLACEHOLDER} team.",
        "summary": "Login is broken for this customer.",
    })

    from app.workflows.implementations.customer_support import run

    result = run({"input": {"issue": "Login is broken"}}, user_id=1)

    assert result["status"] == "ok"
    assert result["triage"]["suggested_action"] == "Escalate to the Sheffield team."
    assert result["triage"]["urgency_reason"] == "Customer is located in [omitted]."
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_hr_recruitment_restores_summary_and_concerns(monkeypatch):
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "score": 60,
        "recommendation": "maybe",
        "strengths": [],
        "concerns": [f"Relocation from {_PLACEHOLDER} may be needed", _UNMAPPED_PLACEHOLDER],
        "interview_questions": [],
        "summary": f"Candidate is currently based in {_PLACEHOLDER}.",
    })

    from app.workflows.implementations.hr_recruitment import run

    result = run({"input": {"candidate_name": "Jan de Vries", "role": "Engineer"}}, user_id=1)

    candidate = result["candidates"][0]
    assert result["status"] == "ok"
    assert candidate["summary"] == "Candidate is currently based in Sheffield."
    assert candidate["concerns"][0] == "Relocation from Sheffield may be needed"
    assert candidate["concerns"][1] == "[omitted]"
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_business_intelligence_restores_summary_and_kpis(monkeypatch):
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "focus_area": "sales",
        "summary": f"Growth is concentrated in {_PLACEHOLDER}.",
        "kpis": [f"Revenue per {_PLACEHOLDER} office", _UNMAPPED_PLACEHOLDER],
        "recommendations": [],
        "priority_level": "medium",
        "action_items": [],
        "risks": [],
    })

    from app.workflows.implementations.business_intelligence import run

    result = run({"input": {"question": "Where should we expand?"}}, user_id=1)

    assert result["status"] == "ok"
    assert result["insights"]["summary"] == "Growth is concentrated in Sheffield."
    assert result["summary"] == "Growth is concentrated in Sheffield."  # top-level mirror
    assert result["insights"]["kpis"][0] == "Revenue per Sheffield office"
    assert result["insights"]["kpis"][1] == "[omitted]"
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_marketing_automation_restores_strategy_summary_and_actions(monkeypatch):
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "strategy_summary": f"Target the {_PLACEHOLDER} market directly.",
        "channels": ["email_sequence"],
        "actions": [f"Localise ads for {_PLACEHOLDER}", _UNMAPPED_PLACEHOLDER],
        "messaging": {"headline": "", "value_proposition": "", "call_to_action": ""},
        "timing": {"launch_recommendation": "", "frequency": "", "duration": ""},
        "roi_estimate": {"direction": "medium", "rationale": "", "expected_metrics": []},
    })

    from app.workflows.implementations.marketing_automation import run

    result = run({"input": {"campaign": "Q1 launch", "audience": "B2B"}}, user_id=1)

    assert result["status"] == "ok"
    assert result["strategy"]["summary"] == "Target the Sheffield market directly."
    assert result["actions"][0] == "Localise ads for Sheffield"
    assert result["actions"][1] == "[omitted]"
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_meeting_agenda_assistant_restores_participant_name_and_summary(monkeypatch):
    """preparation_tips[].participant is the highest-risk field in this
    workflow — the LLM is explicitly asked to echo a participant name/role
    back (see the system prompt), so this is the one place in the whole
    Batch J scope where an anonymized PERSON placeholder is most likely to
    appear verbatim if restoration were missing."""
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "agenda": [{"topic": f"Welcome from {_PLACEHOLDER}", "duration_min": 5, "desired_outcome": "", "facilitator_notes": ""}],
        "preparation_tips": [
            {"participant": _PLACEHOLDER, "tips": [f"Prepare notes about {_PLACEHOLDER}"]},
            {"participant": _UNMAPPED_PLACEHOLDER, "tips": []},
        ],
        "decision_points": [],
        "action_items_template": [],
        "meeting_summary": f"Kickoff with the {_PLACEHOLDER} team.",
    })

    from app.workflows.implementations.meeting_agenda_assistant import run

    result = run({"input": {"title": "Kickoff", "duration_min": 30, "participants": ["Alice"]}}, user_id=1)

    assert result["status"] == "ok"
    assert result["preparation_tips"][0]["participant"] == "Sheffield"
    assert result["preparation_tips"][0]["tips"][0] == "Prepare notes about Sheffield"
    assert result["preparation_tips"][1]["participant"] == "[omitted]"
    assert result["meeting_summary"] == "Kickoff with the Sheffield team."
    assert result["agenda"][0]["topic"] == "Welcome from Sheffield"
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_invoice_processing_restores_vendor_and_summary(monkeypatch):
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "invoice_number": "INV-1",
        "invoice_date": "2026-10-01",
        "vendor": {"name": "Acme Ltd", "address": f"1 Main St, {_PLACEHOLDER}", "vat_number": None},
        "currency": "GBP",
        "line_items": [{"description": f"Service in {_UNMAPPED_PLACEHOLDER}", "quantity": 1, "unit_price": 100, "line_total": 100}],
        "subtotal": 100,
        "vat_rate": 0.2,
        "vat_amount": 20,
        "total_amount": 120,
        "anomalies": [],
        "summary": f"Invoice from a vendor in {_PLACEHOLDER}.",
    })

    from app.workflows.implementations.invoice_processing import run

    result = run({"input": {"invoice_text": "Invoice 123, 1 Main St, [location], total 120 GBP"}}, user_id=1)

    assert result["status"] == "ok"
    assert result["vendor"]["address"] == "1 Main St, Sheffield"
    assert result["summary"] == "Invoice from a vendor in Sheffield."
    assert result["line_items"][0]["description"] == "Service in [omitted]"
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_compliance_monitoring_restores_summary_and_findings(monkeypatch):
    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "compliance_score": 70,
        "risk_level": "medium",
        "findings": [
            {
                "issue": f"Policy does not mention {_PLACEHOLDER}",
                "severity": "medium",
                "framework_ref": "ISO 42001",
                "recommendation": f"Add a clause covering {_UNMAPPED_PLACEHOLDER}",
            }
        ],
        "recommendations": [f"Review governance for the {_PLACEHOLDER} office"],
        "framework_alignment": ["ISO 42001"],
        "summary": f"Overall posture is reasonable for the {_PLACEHOLDER} entity.",
    })

    from app.workflows.implementations.compliance_monitoring import run

    result = run({"input": {"policy_text": "All systems require review."}}, user_id=1, org_id=1)

    assert result["status"] == "ok"
    assert result["summary"] == "Overall posture is reasonable for the Sheffield entity."
    assert result["recommendations"][0] == "Review governance for the Sheffield office"
    assert result["findings"][0]["issue"] == "Policy does not mention Sheffield"
    assert result["findings"][0]["recommendation"] == "Add a clause covering [omitted]"
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)


def test_document_knowledge_restores_answer_and_reasoning(monkeypatch, tmp_path):
    from pathlib import Path

    from tests.conftest import ensure_document

    org_dir = Path("uploaded_documents/org_1")
    org_dir.mkdir(parents=True, exist_ok=True)
    stored_name = "pii_restore_wiring_test_doc.txt"
    content = "The Sheffield office follows policy X for all audits."
    (org_dir / stored_name).write_text(content, encoding="utf-8")
    ensure_document(
        organization_id=1,
        uploaded_by_user_id=1,
        filename=stored_name,
        stored_name=stored_name,
        path=str(org_dir / stored_name),
        content_type="text/plain",
        size=len(content),
    )

    _fixed_mapping_anonymize(monkeypatch)
    mock_openai_response(monkeypatch, {
        "answer": f"Policy X applies to the {_PLACEHOLDER} office.",
        "confidence": "high",
        "sources_used": [stored_name],
        "reasoning": f"The document also mentions {_UNMAPPED_PLACEHOLDER}.",
    })

    from app.workflows.implementations.document_knowledge import run

    result = run(
        payload={"input": {"question": "Where does policy X apply?", "documents": [stored_name]}, "context": {}, "org_id": 1},
        user_id=1,
    )

    assert result["status"] == "ok"
    assert result["answer"]["summary"] == "Policy X applies to the Sheffield office."
    assert result["answer"]["reasoning"] == "The document also mentions [omitted]."
    assert _PLACEHOLDER not in str(result)
    assert _UNMAPPED_PLACEHOLDER not in str(result)
