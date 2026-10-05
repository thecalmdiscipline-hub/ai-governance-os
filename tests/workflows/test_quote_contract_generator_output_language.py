"""Tests for the output_language parameter and the PII placeholder-restore
wiring added to Quote & Contract Generator on 2026-10-05 (see CLAUDE.md §6).

Two real findings from a production demo run drove this:
  1. The workflow's narrative text was always Dutch, regardless of the
     client's language — output_language fixes that.
  2. The client's own address was anonymized before the OpenAI call (as
     designed, for every workflow), but the raw "<LOCATIE>" placeholder
     was never substituted back, so it leaked literally into the
     generated quote text. This file tests the restore wiring that fixes
     that specifically for this workflow (see app/core/pii_anonymizer.py
     for the shared mapping/restore mechanism itself, tested in
     tests/test_pii_anonymizer.py).
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core import pii_anonymizer
from app.main import app
from app.workflows.services.runner import run_workflow

# NOT "from app.workflows.implementations import quote_contract_generator"
# and NOT "import app.workflows.implementations.quote_contract_generator as
# qcg" — app/workflows/implementations/__init__.py does
# `from .quote_contract_generator import quote_contract_generator`, which
# rebinds the PACKAGE's `quote_contract_generator` attribute to the
# function of that name. Both of those import forms resolve through that
# (now-shadowed) attribute, so `qcg` would end up being the function, not
# the module. importlib.import_module() reads straight from sys.modules
# and gets the real module.
qcg = importlib.import_module("app.workflows.implementations.quote_contract_generator")

client = TestClient(app)

_MINIMAL_PAYLOAD = {
    "input": {
        "customer": {"name": "Jan de Vries", "email": "jan@acme.nl", "company": "ACME"},
        "items": [{"description": "Consulting", "qty": 1, "unit_price": 100}],
    },
    "context": {},
}


# ---------------------------------------------------------------------------
# resolve_output_language() — pure function, no mocking needed.
# ---------------------------------------------------------------------------

def test_resolve_output_language_defaults_missing_to_nl():
    assert qcg.resolve_output_language(None) == "nl"


def test_resolve_output_language_defaults_empty_string_to_nl():
    assert qcg.resolve_output_language("") == "nl"
    assert qcg.resolve_output_language("   ") == "nl"


def test_resolve_output_language_accepts_nl_and_en_case_insensitively():
    assert qcg.resolve_output_language("nl") == "nl"
    assert qcg.resolve_output_language("NL") == "nl"
    assert qcg.resolve_output_language("en") == "en"
    assert qcg.resolve_output_language(" En ") == "en"


def test_resolve_output_language_rejects_unsupported_value():
    assert qcg.resolve_output_language("fr") is None
    assert qcg.resolve_output_language("dutch") is None


# ---------------------------------------------------------------------------
# Capturing fake OpenAI client — records the exact messages sent, so we can
# assert which system prompt / labels were actually used, without needing
# a real model.
# ---------------------------------------------------------------------------

def _make_capturing_openai(content, calls, tokens=42):
    class _Completions:
        def create(self, *args, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=SimpleNamespace(total_tokens=tokens),
            )

    class _Chat:
        completions = _Completions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _Chat()

    return _FakeOpenAI


_OK_CONTENT = (
    '{"quote_text": "Generated quote.", "scope_description": "Scope.", '
    '"enhanced_items": [], "contract_terms": ["Term 1.", "Term 2."], '
    '"payment_note": "Pay on time.", "validity_note": "Valid 14 days.", '
    '"special_conditions": []}'
)


# ---------------------------------------------------------------------------
# output_language selects the system prompt and the user-message labels.
# ---------------------------------------------------------------------------

def test_omitted_output_language_uses_dutch_system_prompt_and_labels(monkeypatch):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    result = run_workflow("quote_contract_generator", _MINIMAL_PAYLOAD, user_id=1, org_id=1)

    assert result["status"] == "ok"
    assert result["output"]["output_language"] == "nl"
    assert len(calls) == 1
    messages = calls[0]["messages"]
    assert messages[0]["content"] == qcg._SYSTEM_PROMPT_NL
    assert "Offerte-aanvraag:" in messages[1]["content"]


def test_explicit_nl_is_identical_to_omitted(monkeypatch):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    payload_explicit_nl = {
        "input": {**_MINIMAL_PAYLOAD["input"], "output_language": "nl"},
        "context": {},
    }
    result_omitted = run_workflow("quote_contract_generator", _MINIMAL_PAYLOAD, user_id=1, org_id=1)
    result_explicit = run_workflow("quote_contract_generator", payload_explicit_nl, user_id=1, org_id=1)

    assert result_omitted["status"] == result_explicit["status"] == "ok"
    # Same system prompt and (apart from the random quote/contract ids,
    # which are not language-dependent) the same user-message content.
    assert calls[0]["messages"][0]["content"] == calls[1]["messages"][0]["content"] == qcg._SYSTEM_PROMPT_NL
    assert calls[0]["messages"][1]["content"] == calls[1]["messages"][1]["content"]


def test_output_language_en_uses_english_system_prompt_and_labels(monkeypatch):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    payload = {"input": {**_MINIMAL_PAYLOAD["input"], "output_language": "en"}, "context": {}}
    result = run_workflow("quote_contract_generator", payload, user_id=1, org_id=1)

    assert result["status"] == "ok"
    assert result["output"]["output_language"] == "en"
    messages = calls[0]["messages"]
    assert messages[0]["content"] == qcg._SYSTEM_PROMPT_EN
    assert "Quote request:" in messages[1]["content"]
    assert "Offerte-aanvraag:" not in messages[1]["content"]
    # The hardcoded "Toepasselijk recht (Nederland)" guidance must not
    # survive into the English prompt unchanged (see module docstring).
    assert "Nederland" not in qcg._SYSTEM_PROMPT_EN


def test_output_language_en_is_case_insensitive_and_trimmed(monkeypatch):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    payload = {"input": {**_MINIMAL_PAYLOAD["input"], "output_language": " EN "}, "context": {}}
    result = run_workflow("quote_contract_generator", payload, user_id=1, org_id=1)

    assert result["status"] == "ok"
    assert result["output"]["output_language"] == "en"


def test_invalid_output_language_does_not_call_openai_and_returns_degraded(monkeypatch):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    payload = {"input": {**_MINIMAL_PAYLOAD["input"], "output_language": "fr"}, "context": {}}
    result = run_workflow("quote_contract_generator", payload, user_id=1, org_id=1)

    assert result["output"]["status"] == "degraded"
    assert calls == []  # never reached the LLM call


# ---------------------------------------------------------------------------
# HTTP-level 422 — the router must reject an unsupported output_language
# before run_workflow() is even called, so it is a real HTTP 422, not a
# 200 with status="error" (which is what run_workflow()'s generic
# try/except would otherwise produce).
# ---------------------------------------------------------------------------

@pytest.fixture
def _grant_quote_contract_generator_to_org_1():
    """org 1 (dennis_admin, used by the TestClient login below) does not
    have quote_contract_generator active in the standard test-seed module
    set (see scripts/seed_modules.py) — grant it just for these HTTP-level
    tests, additively (skipped if already present), so require_module_access
    doesn't 403 before the router's own validation is ever reached."""
    from app.db.session import SessionLocal
    from app.models.tenant_module import TenantModule

    db = SessionLocal()
    try:
        existing = (
            db.query(TenantModule)
            .filter(TenantModule.organization_id == 1, TenantModule.module_key == "quote_contract_generator")
            .first()
        )
        if existing is None:
            db.add(TenantModule(organization_id=1, module_key="quote_contract_generator", is_active=True))
            db.commit()
        elif not existing.is_active:
            existing.is_active = True
            db.commit()
    finally:
        db.close()
    yield


def _login_token() -> str:
    res = client.post(
        "/login",
        data={"username": "dennis_admin", "password": "Admin123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_invalid_output_language_returns_http_422(monkeypatch, _grant_quote_contract_generator_to_org_1):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    token = _login_token()
    res = client.post(
        "/workflows/quote-contract-generator/run",
        json={"input": {**_MINIMAL_PAYLOAD["input"], "output_language": "fr"}, "context": {}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 422
    assert res.json()["error"] == "invalid_output_language"
    assert set(res.json()["allowed"]) == {"nl", "en"}
    assert calls == []  # the router rejected it before run_workflow() ever ran


def test_valid_output_language_reaches_the_workflow_via_http(monkeypatch, _grant_quote_contract_generator_to_org_1):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    token = _login_token()
    res = client.post(
        "/workflows/quote-contract-generator/run",
        json={"input": {**_MINIMAL_PAYLOAD["input"], "output_language": "en"}, "context": {}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["output"]["output_language"] == "en"


def test_missing_output_language_still_reaches_the_workflow_via_http(monkeypatch, _grant_quote_contract_generator_to_org_1):
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    token = _login_token()
    res = client.post(
        "/workflows/quote-contract-generator/run",
        json={"input": _MINIMAL_PAYLOAD["input"], "context": {}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json()["output"]["output_language"] == "nl"


# ---------------------------------------------------------------------------
# PII placeholder restore wiring — the workflow must restore a known
# placeholder and must never show an unresolved one raw. pii_anonymizer
# itself is mocked here (its real detection behaviour is covered by
# tests/test_pii_anonymizer.py) — this file only tests that the workflow
# wires the mapping it gets through to restore_placeholders() correctly
# for every narrative output field.
# ---------------------------------------------------------------------------

def test_restores_known_placeholder_in_quote_text_and_contract_terms(monkeypatch):
    import openai

    def _fake_anonymize_with_mapping(text, workflow=None):
        return text, {"<LOCATIE>": "Sheffield, UK"}

    monkeypatch.setattr(pii_anonymizer, "anonymize_text_with_mapping", _fake_anonymize_with_mapping)

    content = (
        '{"quote_text": "Thank you for your enquiry about our office in <LOCATIE>.", '
        '"scope_description": "Work takes place in <LOCATIE>.", '
        '"enhanced_items": [], '
        '"contract_terms": ["Governing law applies as per <LOCATIE>."], '
        '"payment_note": "", "validity_note": "", "special_conditions": []}'
    )
    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(content, calls))

    payload = {"input": {**_MINIMAL_PAYLOAD["input"], "output_language": "en"}, "context": {}}
    result = run_workflow("quote_contract_generator", payload, user_id=1, org_id=1)

    output = result["output"]
    assert output["status"] == "ok"
    assert "<LOCATIE>" not in output["quote_text"]
    assert "Sheffield, UK" in output["quote_text"]
    assert "Sheffield, UK" in output["scope_description"]
    assert "Sheffield, UK" in output["contract_terms"][0]
    assert "<LOCATIE>" not in output["contract_terms"][0]


def test_unresolved_placeholder_is_not_shown_raw_in_output(monkeypatch):
    import openai

    def _fake_anonymize_with_mapping(text, workflow=None):
        # Empty mapping simulates: the LLM produced a placeholder-shaped
        # token that this request's anonymization never actually created
        # (mangled/paraphrased/invented) — nothing to restore it with.
        return text, {}

    monkeypatch.setattr(pii_anonymizer, "anonymize_text_with_mapping", _fake_anonymize_with_mapping)

    content = (
        '{"quote_text": "Our office is in <LOCATIE>.", "scope_description": "", '
        '"enhanced_items": [], "contract_terms": [], '
        '"payment_note": "", "validity_note": "", "special_conditions": []}'
    )
    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(content, calls))

    result = run_workflow("quote_contract_generator", _MINIMAL_PAYLOAD, user_id=1, org_id=1)

    output = result["output"]
    assert output["status"] == "ok"
    assert "<LOCATIE>" not in output["quote_text"]
    assert pii_anonymizer._UNRESOLVED_PLACEHOLDER_FILLER in output["quote_text"]


def test_item_descriptions_are_also_restored(monkeypatch):
    import openai

    def _fake_anonymize_with_mapping(text, workflow=None):
        return text, {"<PERSOON>": "Jan de Vries"}

    monkeypatch.setattr(pii_anonymizer, "anonymize_text_with_mapping", _fake_anonymize_with_mapping)

    content = (
        '{"quote_text": "", "scope_description": "", '
        '"enhanced_items": [{"original_description": "Consulting", '
        '"professional_description": "Consulting services for <PERSOON>."}], '
        '"contract_terms": [], "payment_note": "", "validity_note": "", "special_conditions": []}'
    )
    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(content, calls))

    result = run_workflow("quote_contract_generator", _MINIMAL_PAYLOAD, user_id=1, org_id=1)

    item_description = result["output"]["items"][0]["description"]
    assert "<PERSOON>" not in item_description
    assert "Jan de Vries" in item_description


def test_fails_closed_when_anonymizer_unavailable(monkeypatch):
    """Switching to anonymize_text_with_mapping() must not weaken the
    existing fail-closed contract: if the anonymizer is unavailable, the
    workflow must still degrade and must still never reach OpenAI."""
    import openai

    calls = []
    monkeypatch.setattr(openai, "OpenAI", _make_capturing_openai(_OK_CONTENT, calls))

    def _raise(text, workflow=None):
        raise pii_anonymizer.PIIAnonymizerUnavailable("simulated failure")

    monkeypatch.setattr(pii_anonymizer, "anonymize_text_with_mapping", _raise)

    result = run_workflow("quote_contract_generator", _MINIMAL_PAYLOAD, user_id=1, org_id=1)

    assert result["output"]["status"] == "degraded"
    assert calls == []
