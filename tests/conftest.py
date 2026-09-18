import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

os.environ["TESTING"] = "1"

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _disable_login_rate_limit():
    try:
        import app.main as main

        for attr in [
            "check_login_rate_limit",
            "rate_limit_login",
            "enforce_login_rate_limit",
            "login_rate_limit_check",
        ]:
            if hasattr(main, attr):
                setattr(main, attr, lambda *args, **kwargs: None)

        for name in [
            "login_attempts",
            "LOGIN_ATTEMPTS",
            "FAILED_LOGIN_ATTEMPTS",
            "RATE_LIMIT_BUCKETS",
            "login_rate_limit_store",
            "LOGIN_RATE_LIMIT_STORE",
        ]:
            if hasattr(main, name):
                value = getattr(main, name)
                if isinstance(value, dict):
                    value.clear()
    except Exception:
        pass


def pytest_configure(config):
    _disable_login_rate_limit()


def pytest_runtest_setup(item):
    _disable_login_rate_limit()


# ---------------------------------------------------------------------------
# OpenAI mocking
#
# Every workflow implementation under app/workflows/implementations/ does
# `import openai; client = openai.OpenAI(api_key=...)` at call time. Without
# mocking, running pytest hits the real OpenAI API on every workflow test —
# burning real credits and making assertions depend on nondeterministic LLM
# output. This fixture patches `openai.OpenAI` for every test by default, so
# no test reaches the network. Tests that need a specific response (because
# they assert on LLM-derived content, e.g. an exact score or extracted
# field) call `mock_openai_response(monkeypatch, {...})` to override the
# default payload for just that test.
# ---------------------------------------------------------------------------

_DEFAULT_MOCK_LLM_CONTENT = {
    # sales_lead_qualification
    "score": 65,
    "qualification": "needs_nurturing",
    "strengths": ["Clear industry fit"],
    "weaknesses": ["Missing budget signal"],
    "next_actions": ["Schedule discovery call"],
    # customer_support
    "priority": "medium",
    "urgency_reason": "Standard support request, no immediate business impact.",
    "suggested_action": "Route to support queue for standard handling.",
    # business_intelligence
    "focus_area": "general",
    "priority_level": "medium",
    "kpis": ["Monthly recurring revenue"],
    "recommendations": ["Review pipeline weekly"],
    "action_items": ["Schedule follow-up review"],
    "risks": ["Data may be incomplete"],
    # hr_recruitment
    "recommendation": "maybe",
    "concerns": ["Limited information provided"],
    "interview_questions": ["Can you describe your relevant experience?"],
    # invoice_processing
    "invoice_number": "TEST-0001",
    "invoice_date": "2026-01-01",
    "vendor": {"name": "Test Vendor BV", "address": "Teststraat 1, Amsterdam", "vat_number": "NL000000000B01"},
    "currency": "EUR",
    "line_items": [
        {"description": "Test service", "quantity": 1, "unit_price": 100.0, "line_total": 100.0}
    ],
    "subtotal": 100.0,
    "vat_rate": 0.21,
    "vat_amount": 21.0,
    "total_amount": 121.0,
    "anomalies": [],
    # document_knowledge
    "answer": "Based on the provided documents, here is the relevant information.",
    "confidence": "medium",
    "sources_used": [],
    "reasoning": "Derived from the supplied document excerpts.",
    # meeting_agenda_assistant
    "agenda": [
        {"topic": "Opening", "duration_min": 5, "desired_outcome": "Align on goals", "facilitator_notes": "Quick check-in"},
        {"topic": "Main discussion", "duration_min": 20, "desired_outcome": "Reach decisions", "facilitator_notes": "Time-box discussion"},
        {"topic": "Wrap-up", "duration_min": 5, "desired_outcome": "Confirm next steps", "facilitator_notes": "Recap action items"},
    ],
    "preparation_tips": [{"participant": "All participants", "tips": ["Review the agenda beforehand"]}],
    "decision_points": ["Confirm next milestone"],
    "action_items_template": ["[Owner] to follow up by [date]"],
    "meeting_summary": "A structured working session to align on goals and next steps.",
    # quote_contract_generator
    "quote_text": "Hierbij ontvangt u onze offerte voor de besproken dienstverlening.",
    "scope_description": "De opdracht omvat de overeengekomen dienstverlening zoals gespecificeerd.",
    "enhanced_items": [],
    "contract_terms": [
        "Betalingstermijn: conform de overeengekomen termijn op de offerte.",
        "Intellectueel eigendom blijft bij levering eigendom van de opdrachtnemer, tenzij anders overeengekomen.",
        "Aansprakelijkheid is beperkt tot het factuurbedrag.",
        "Partijen zijn verplicht tot geheimhouding van vertrouwelijke informatie.",
        "Opzegging is mogelijk met inachtneming van een opzegtermijn van 30 dagen.",
        "Op deze overeenkomst is Nederlands recht van toepassing.",
    ],
    "payment_note": "Betaling dient te geschieden binnen de overeengekomen termijn.",
    "validity_note": "Deze offerte is geldig tot de vermelde geldigheidsdatum.",
    "special_conditions": [],
    # marketing_automation
    "strategy_summary": "A multi-channel B2B strategy focused on the target audience.",
    "channels": ["email_sequence", "linkedin_organic"],
    "actions": ["Draft outreach sequence", "Publish supporting content"],
    "messaging": {
        "headline": "Take control of your AI governance",
        "value_proposition": "Structured oversight without slowing teams down",
        "call_to_action": "Request a demo",
    },
    "timing": {
        "launch_recommendation": "Launch mid-week, avoid holiday periods",
        "frequency": "2x per week",
        "duration": "4-week campaign",
    },
    "roi_estimate": {
        "direction": "medium",
        "rationale": "Reasonable audience-channel fit with standard B2B execution.",
        "expected_metrics": ["Reply rate", "Meetings booked"],
    },
    # compliance_monitoring
    "compliance_score": 75,
    "risk_level": "medium",
    "findings": [],
    "framework_alignment": ["ISO 42001"],
    "summary": "Baseline compliance posture appears reasonable; periodic review recommended.",
}


def _make_fake_openai(content, tokens=150):
    raw = json.dumps(content)

    class _FakeCompletions:
        def create(self, *args, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
                usage=SimpleNamespace(total_tokens=tokens),
            )

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    return _FakeOpenAI


def mock_openai_response(monkeypatch, content, tokens=150):
    """Override the mocked OpenAI chat-completion response for the current test only."""
    import openai

    monkeypatch.setattr(openai, "OpenAI", _make_fake_openai(content, tokens))


@pytest.fixture(autouse=True)
def _mock_openai_by_default(monkeypatch):
    import openai

    monkeypatch.setattr(openai, "OpenAI", _make_fake_openai(_DEFAULT_MOCK_LLM_CONTENT))
    yield


# ---------------------------------------------------------------------------
# PII-anonimisering mocking (app/core/pii_anonymizer.py)
#
# Every workflow implementation now does
# `from app.core import pii_anonymizer` and calls
# `pii_anonymizer.anonymize_text(user_message, workflow=...)` right before
# the OpenAI call (see CLAUDE.md §5, "Geen AVG-anonimisering vóór
# LLM-calls"). Real anonymize_text() lazily loads Presidio + two spaCy
# language models on first use — slow, and not guaranteed to be installed
# in every environment that runs this test suite. By default we patch it
# to a fast no-op passthrough so the ~200 existing workflow tests keep
# running deterministically without needing spaCy models installed.
#
# Tests that specifically exercise the anonymizer's own behaviour (see
# tests/test_pii_anonymizer.py) should NOT rely on this fixture — they
# either monkeypatch pii_anonymizer.anonymize_text explicitly per-test, or
# (for the real-detection tests) are skipped when presidio/spacy are not
# importable.
#
# Because every workflow does `from app.core import pii_anonymizer` (module
# import, not `from ... import anonymize_text`), patching the single
# attribute on the pii_anonymizer module is enough to affect every workflow
# — mirroring how `monkeypatch.setattr(openai, "OpenAI", ...)` above works
# for the OpenAI mock.
# ---------------------------------------------------------------------------


def _identity_anonymize_text(text, workflow=None):
    return text


def mock_pii_unavailable(monkeypatch, message="PII-anonimisering is niet beschikbaar (test)"):
    """Make the next anonymize_text() call raise PIIAnonymizerUnavailable.

    Use this to assert a workflow's fail-closed behaviour: it must return a
    "degraded" response and must NEVER fall back to sending unanonymized
    text to OpenAI.
    """
    from app.core import pii_anonymizer

    def _raise(text, workflow=None):
        raise pii_anonymizer.PIIAnonymizerUnavailable(message)

    monkeypatch.setattr(pii_anonymizer, "anonymize_text", _raise)


@pytest.fixture(autouse=True)
def _mock_pii_anonymizer_by_default(monkeypatch):
    from app.core import pii_anonymizer

    monkeypatch.setattr(pii_anonymizer, "anonymize_text", _identity_anonymize_text)
    yield


# ---------------------------------------------------------------------------
# Shared DB fixtures for tests that depend on ambient rows (documents,
# tenant module activation) rather than creating their own isolated state.
# ---------------------------------------------------------------------------

def ensure_document(
    *,
    organization_id,
    uploaded_by_user_id,
    filename,
    stored_name,
    path,
    content_type="text/plain",
    size=0,
):
    """Get-or-recreate a Document row by stored_name (globally unique column).

    Idempotent across repeated local test runs against the same test.db —
    without this, a second run fails with a UNIQUE constraint violation
    because the previous run's row is still present.
    """
    from app.db.session import SessionLocal
    from app.models.document import Document

    db = SessionLocal()
    try:
        existing = db.query(Document).filter(Document.stored_name == stored_name).first()
        if existing is not None:
            db.delete(existing)
            db.commit()

        doc = Document(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            stored_name=stored_name,
            path=path,
            content_type=content_type,
            size=size,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    finally:
        db.close()
