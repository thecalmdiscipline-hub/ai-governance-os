"""Verifies every workflow actually calls the PII-anonimiseringslaag before
sending anything to OpenAI, and that it fails CLOSED (never falls back to
sending raw, unanonymized text) when the anonymizer itself is unavailable.

This is the test that directly backs the "Geen AVG-anonimisering vóór
LLM-calls" risico fix in CLAUDE.md §5: it does not test Presidio's
detection quality (see tests/test_pii_anonymizer.py for that) — it tests
the WIRING, i.e. that app.core.pii_anonymizer.anonymize_text() is on the
path between `_build_user_message(...)` and every `client.chat.completions
.create(...)` call, for all 10 workflows, with no exceptions.

Uses the same `import openai; openai.OpenAI(...)` — style patching as the
existing `mock_openai_response()` helper in conftest.py, plus
`mock_pii_unavailable()` (added alongside it) to simulate the anonymizer
failing to initialize.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import pii_anonymizer
from tests.conftest import ensure_document, mock_pii_unavailable

# (module path, workflow key, minimal valid payload, extra run() kwargs)
#
# Every payload is chosen so the workflow actually reaches the LLM call path
# (not an early "no API key" / "no input" guard) — mirroring the minimal
# valid payloads used in the existing tests/workflows/test_*_impl.py files.
WORKFLOWS = [
    (
        "app.workflows.implementations.sales_lead_qualification",
        "sales_lead_qualification",
        {"input": {"lead": {"email": "jan@acme.nl", "company": "ACME"}}, "context": {}},
        {"user_id": 1},
    ),
    (
        "app.workflows.implementations.invoice_processing",
        "invoice_processing",
        {"input": {"invoice_text": "Invoice 123 amount 500 EUR due 14 days"}},
        {"user_id": 1, "org_id": 1},
    ),
    (
        "app.workflows.implementations.customer_support",
        "customer_support",
        {"input": {"issue": "Login is broken", "customer_name": "Jan de Vries"}},
        {"user_id": 1},
    ),
    (
        "app.workflows.implementations.hr_recruitment",
        "hr_recruitment",
        {"input": {"candidate_name": "Jan de Vries", "role": "Engineer", "resume": "5 years Python."}},
        {"user_id": 1, "org_id": 1},
    ),
    (
        "app.workflows.implementations.marketing_automation",
        "marketing_automation",
        {"input": {"campaign": "Q1 launch", "audience": "B2B SaaS founders", "product": "Valqeron Core"}},
        {"user_id": 1, "org_id": 1},
    ),
    (
        "app.workflows.implementations.meeting_agenda_assistant",
        "meeting_agenda_assistant",
        {"input": {"title": "Kickoff", "participants": ["Jan", "Piet"], "goals": "Align on scope"}},
        {"user_id": 1, "org_id": 1},
    ),
    (
        "app.workflows.implementations.quote_contract_generator",
        "quote_contract_generator",
        {
            "input": {
                "customer": {"name": "Jan de Vries", "email": "jan@acme.nl", "company": "ACME"},
                "items": [{"description": "Consulting", "qty": 1, "unit_price": 100}],
            }
        },
        {"user_id": 1, "org_id": 1},
    ),
    (
        "app.workflows.implementations.business_intelligence",
        "business_intelligence",
        {"input": {"question": "What is our churn risk this quarter?"}},
        {"user_id": 1, "org_id": 1},
    ),
    (
        "app.workflows.implementations.compliance_monitoring",
        "compliance_monitoring",
        {"input": {"policy_text": "All AI systems require a risk assessment before production."}},
        {"user_id": 1, "org_id": 1},
    ),
]


def _make_tracking_openai(create_calls):
    class _TrackedCompletions:
        def create(self, *args, **kwargs):
            create_calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
                usage=SimpleNamespace(total_tokens=1),
            )

    class _TrackedChat:
        completions = _TrackedCompletions()

    class _TrackedOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _TrackedChat()

    return _TrackedOpenAI


@pytest.mark.parametrize("module_path,workflow_key,payload,kwargs", WORKFLOWS, ids=[w[1] for w in WORKFLOWS])
def test_workflow_calls_anonymize_text_with_its_own_workflow_key(monkeypatch, module_path, workflow_key, payload, kwargs):
    calls = []

    def _spy(text, workflow=None):
        calls.append(workflow)
        return text

    monkeypatch.setattr(pii_anonymizer, "anonymize_text", _spy)

    run = importlib.import_module(module_path).run
    result = run(payload, **kwargs)

    assert calls == [workflow_key], (
        f"{workflow_key}: expected exactly one anonymize_text() call with "
        f"workflow={workflow_key!r}, got {calls!r}"
    )
    assert result["status"] == "ok"


@pytest.mark.parametrize("module_path,workflow_key,payload,kwargs", WORKFLOWS, ids=[w[1] for w in WORKFLOWS])
def test_workflow_fails_closed_when_anonymizer_unavailable(monkeypatch, module_path, workflow_key, payload, kwargs):
    import openai

    create_calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_tracking_openai(create_calls))
    mock_pii_unavailable(monkeypatch, f"gesimuleerde storing ({workflow_key})")

    run = importlib.import_module(module_path).run
    result = run(payload, **kwargs)

    assert result["status"] == "degraded", (
        f"{workflow_key}: must return status='degraded' when the PII-anonimiseringslaag "
        f"is unavailable — got {result.get('status')!r}. Falling back to 'ok' here would "
        f"mean raw, unanonymized text was sent to OpenAI."
    )
    assert create_calls == [], (
        f"{workflow_key}: OpenAI chat.completions.create() was called even though the "
        f"PII-anonimiseringslaag failed to initialize — this is exactly the AVG leak "
        f"this layer exists to prevent."
    )


# ---------------------------------------------------------------------------
# document_knowledge needs an actual document on disk + in the DB to reach
# the LLM call path (see tests/workflows/test_document_knowledge_impl.py for
# the same setup pattern) — kept separate from the table above for that
# reason.
# ---------------------------------------------------------------------------

def _setup_document_knowledge_fixture_document():
    org_dir = Path("uploaded_documents/org_1")
    org_dir.mkdir(parents=True, exist_ok=True)

    stored_name = "pii_wiring_test_doc.txt"
    content = "Policy X requires all AI systems to undergo a risk assessment before production approval."
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
    return stored_name


def test_document_knowledge_calls_anonymize_text_with_its_own_workflow_key(monkeypatch):
    stored_name = _setup_document_knowledge_fixture_document()

    calls = []

    def _spy(text, workflow=None):
        calls.append(workflow)
        return text

    monkeypatch.setattr(pii_anonymizer, "anonymize_text", _spy)

    from app.workflows.implementations.document_knowledge import run

    result = run(
        payload={
            "input": {"question": "Where is policy X?", "documents": [stored_name]},
            "context": {},
            "org_id": 1,
        },
        user_id=1,
    )

    assert calls == ["document_knowledge"]
    assert result["status"] == "ok"


def test_document_knowledge_fails_closed_when_anonymizer_unavailable(monkeypatch):
    stored_name = _setup_document_knowledge_fixture_document()

    import openai

    create_calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_tracking_openai(create_calls))
    mock_pii_unavailable(monkeypatch, "gesimuleerde storing (document_knowledge)")

    from app.workflows.implementations.document_knowledge import run

    result = run(
        payload={
            "input": {"question": "Where is policy X?", "documents": [stored_name]},
            "context": {},
            "org_id": 1,
        },
        user_id=1,
    )

    assert result["status"] == "degraded"
    assert create_calls == []
