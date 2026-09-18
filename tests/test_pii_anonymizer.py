"""Tests for app/core/pii_anonymizer.py — the AVG-anonimiseringslaag.

Two tiers:
  1. Pure-logic unit tests (BSN-checksum, blank-text short-circuit,
     entity-set overrides) — always run, no Presidio/spaCy required, since
     PIIAnonymizerUnavailable / the BSN validator have no import-time
     dependency on presidio.
  2. Real end-to-end detection tests against the actual Presidio+spaCy
     pipeline — skipped automatically when presidio/spacy (or the spaCy
     language models) are not installed in this environment, so this file
     never breaks a plain `pytest -q` run on a machine without the (large)
     spaCy models. Run these deliberately with the real dependencies
     installed to confirm the anonymizer actually detects what it should.

Note: the autouse `_mock_pii_anonymizer_by_default` fixture in conftest.py
patches `pii_anonymizer.anonymize_text` to a no-op for every OTHER test in
this suite (see conftest.py for why). This file exercises the real
`anonymize_text` directly and must not rely on that fixture's mock —
tests below call the module's functions explicitly rather than through a
mocked workflow.
"""
from __future__ import annotations

import importlib

import pytest

from app.core import pii_anonymizer

# Captured at collection time, before any fixture has a chance to monkeypatch
# pii_anonymizer.anonymize_text — this is the real implementation.
_REAL_ANONYMIZE_TEXT = pii_anonymizer.anonymize_text


@pytest.fixture(autouse=True)
def _use_real_anonymize_text(monkeypatch, _mock_pii_anonymizer_by_default):
    """Undo conftest.py's autouse identity-mock for every test in this file.

    conftest.py patches `pii_anonymizer.anonymize_text` to a no-op
    passthrough by default, so the ~200 workflow tests don't need Presidio
    installed. This file's whole purpose is to exercise the REAL
    anonymize_text, so it must restore it — depending on
    `_mock_pii_anonymizer_by_default` by name guarantees this fixture runs
    *after* that one, so ours is the one that wins.
    """
    monkeypatch.setattr(pii_anonymizer, "anonymize_text", _REAL_ANONYMIZE_TEXT)
    yield


def _presidio_available() -> bool:
    try:
        importlib.import_module("presidio_analyzer")
        importlib.import_module("presidio_anonymizer")
        importlib.import_module("spacy")
    except ImportError:
        return False
    return True


requires_presidio = pytest.mark.skipif(
    not _presidio_available(),
    reason="presidio-analyzer/presidio-anonymizer/spacy not installed in this environment",
)


# ---------------------------------------------------------------------------
# BSN 11-proef validator — pure arithmetic, no external dependency.
# ---------------------------------------------------------------------------

def test_bsn_validator_accepts_known_valid_bsn():
    # 111222333 is a commonly used publicly-documented *valid* test BSN
    # (passes the 11-proef) used in Dutch government test environments —
    # safe to hardcode, it is not a real person's number.
    assert pii_anonymizer._is_valid_nl_bsn("111222333") is True


def test_bsn_validator_rejects_arbitrary_digit_string():
    # A plain sequential/arbitrary 9-digit string (e.g. an invoice number)
    # must NOT validate as a BSN, or every invoice number would be flagged.
    assert pii_anonymizer._is_valid_nl_bsn("123456789") is False


def test_bsn_validator_rejects_wrong_length():
    assert pii_anonymizer._is_valid_nl_bsn("1234567") is False
    assert pii_anonymizer._is_valid_nl_bsn("1234567890") is False


def test_bsn_validator_rejects_non_digits():
    assert pii_anonymizer._is_valid_nl_bsn("12a456789") is False


# ---------------------------------------------------------------------------
# Blank/empty input short-circuits before touching Presidio at all — this
# must work even without presidio installed, since it never calls
# _get_engines().
# ---------------------------------------------------------------------------

def test_anonymize_text_empty_string_is_returned_unchanged():
    assert pii_anonymizer.anonymize_text("") == ""


def test_anonymize_text_whitespace_only_is_returned_unchanged():
    assert pii_anonymizer.anonymize_text("   \n\t  ") == "   \n\t  "


# ---------------------------------------------------------------------------
# Entity-set configuration — pure data, no Presidio needed to check it.
# ---------------------------------------------------------------------------

def test_invoice_processing_has_a_reduced_entity_set():
    # invoice_processing must extract vendor.name / vendor.address FROM the
    # LLM's reading of the invoice text (no other source exists — see the
    # workflow's own docstring) — so PERSON and LOCATION must NOT be in its
    # entity set, unlike every other workflow.
    entities = pii_anonymizer.ENTITY_SETS["invoice_processing"]
    assert "PERSON" not in entities
    assert "LOCATION" not in entities
    # Strong individual identifiers must still be covered.
    for strong_identifier in ("EMAIL_ADDRESS", "PHONE_NUMBER", "IBAN_CODE", "NL_BSN"):
        assert strong_identifier in entities


def test_default_entity_set_includes_person_and_location():
    assert "PERSON" in pii_anonymizer._DEFAULT_ENTITIES
    assert "LOCATION" in pii_anonymizer._DEFAULT_ENTITIES


def test_unknown_workflow_falls_back_to_default_entity_set():
    # anonymize_text() looks up ENTITY_SETS.get(workflow, _DEFAULT_ENTITIES)
    # — any workflow key not explicitly overridden must get the full,
    # safest set rather than silently under-anonymizing.
    assert pii_anonymizer.ENTITY_SETS.get("some_future_workflow", pii_anonymizer._DEFAULT_ENTITIES) == (
        pii_anonymizer._DEFAULT_ENTITIES
    )


# ---------------------------------------------------------------------------
# Fail-closed contract: if Presidio/spaCy cannot initialize, anonymize_text
# must raise PIIAnonymizerUnavailable rather than silently returning the
# raw text. Simulated here by monkeypatching the internal init function to
# fail, so this test runs even without presidio installed.
# ---------------------------------------------------------------------------

def test_anonymize_text_raises_when_engine_init_fails(monkeypatch):
    monkeypatch.setattr(pii_anonymizer, "_analyzer", None)
    monkeypatch.setattr(pii_anonymizer, "_anonymizer_engine", None)
    monkeypatch.setattr(pii_anonymizer, "_init_error", None)

    def _boom():
        raise RuntimeError("simulated init failure")

    monkeypatch.setattr(pii_anonymizer, "_init_analyzer", _boom)

    with pytest.raises(pii_anonymizer.PIIAnonymizerUnavailable):
        pii_anonymizer.anonymize_text("Jan de Vries werkt bij ACME.", workflow="sales_lead_qualification")


def test_anonymize_text_remembers_init_failure_without_retrying(monkeypatch):
    # After a first failed init, subsequent calls must raise immediately
    # from the cached _init_error rather than re-attempting a slow,
    # repeatedly-failing import/model-load on every workflow call.
    #
    # `_get_engines()` does `from presidio_anonymizer import AnonymizerEngine`
    # as the very first line inside its try block, before ever reaching
    # `_init_analyzer()`. In an environment where presidio_anonymizer isn't
    # installed at all, that import fails immediately and our
    # `_init_analyzer` mock would never even be reached — so we inject a
    # stand-in module into sys.modules to make that import succeed
    # regardless of what's actually installed, letting execution reach
    # (our mocked) `_init_analyzer()` where the "simulated failure"
    # actually needs to happen for this test to mean anything.
    import sys
    import types

    monkeypatch.setattr(pii_anonymizer, "_analyzer", None)
    monkeypatch.setattr(pii_anonymizer, "_anonymizer_engine", None)
    monkeypatch.setattr(pii_anonymizer, "_init_error", None)

    fake_presidio_anonymizer = types.ModuleType("presidio_anonymizer")
    fake_presidio_anonymizer.AnonymizerEngine = object  # never actually reached
    monkeypatch.setitem(sys.modules, "presidio_anonymizer", fake_presidio_anonymizer)

    call_count = {"n": 0}

    def _boom():
        call_count["n"] += 1
        raise RuntimeError("simulated init failure")

    monkeypatch.setattr(pii_anonymizer, "_init_analyzer", _boom)

    with pytest.raises(pii_anonymizer.PIIAnonymizerUnavailable):
        pii_anonymizer.anonymize_text("tekst 1")
    with pytest.raises(pii_anonymizer.PIIAnonymizerUnavailable):
        pii_anonymizer.anonymize_text("tekst 2")

    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Overlap resolution between the NL and EN analysis passes — pure logic,
# operates on lightweight stand-in objects rather than real Presidio
# RecognizerResult instances, so no presidio install required.
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, start, end, score, entity_type="PERSON"):
        self.start = start
        self.end = end
        self.score = score
        self.entity_type = entity_type


def test_resolve_overlaps_prefers_higher_score():
    low = _FakeResult(0, 10, 0.4)
    high = _FakeResult(0, 10, 0.9)
    resolved = pii_anonymizer._resolve_overlaps([low, high])
    assert resolved == [high]


def test_resolve_overlaps_keeps_non_overlapping_spans():
    a = _FakeResult(0, 5, 0.6)
    b = _FakeResult(10, 15, 0.6)
    resolved = pii_anonymizer._resolve_overlaps([a, b])
    assert resolved == [a, b]


# ---------------------------------------------------------------------------
# Real end-to-end detection — only runs when Presidio + spaCy models are
# actually installed (see requirements.txt for the pinned versions/model
# wheels this depends on).
# ---------------------------------------------------------------------------

@requires_presidio
def test_anonymize_text_redacts_dutch_name_and_email():
    text = "Contactpersoon: Jan de Vries, e-mail jan.devries@acme.nl, telefoon 06-12345678."
    result = pii_anonymizer.anonymize_text(text, workflow="sales_lead_qualification")

    assert "Jan de Vries" not in result
    assert "jan.devries@acme.nl" not in result
    assert "<PERSOON>" in result
    assert "<E-MAILADRES>" in result


@requires_presidio
def test_anonymize_text_redacts_iban_and_bsn():
    text = "IBAN: NL91ABNA0417164300. BSN van de aanvrager: 111222333."
    result = pii_anonymizer.anonymize_text(text, workflow="document_knowledge")

    assert "NL91ABNA0417164300" not in result
    assert "111222333" not in result
    assert "<REKENINGNUMMER>" in result
    assert "<BSN>" in result


@requires_presidio
def test_anonymize_text_for_invoice_processing_keeps_vendor_name_and_address():
    # The reduced entity set for invoice_processing must NOT touch PERSON
    # or LOCATION, so vendor identity/address stay extractable.
    text = "Leverancier: ACME Consultancy BV, Hoofdstraat 1, 1234 AB Amsterdam."
    result = pii_anonymizer.anonymize_text(text, workflow="invoice_processing")

    assert "ACME Consultancy BV" in result
    assert "Hoofdstraat 1" in result
    assert "Amsterdam" in result


@requires_presidio
def test_anonymize_text_for_invoice_processing_still_redacts_email_and_iban():
    text = "Vragen? Bel Jan op 06-12345678 of mail jan@leverancier.nl. Rekeningnummer: NL91ABNA0417164300."
    result = pii_anonymizer.anonymize_text(text, workflow="invoice_processing")

    assert "jan@leverancier.nl" not in result
    assert "NL91ABNA0417164300" not in result


@requires_presidio
def test_anonymize_text_no_pii_returns_text_unchanged():
    text = "Dit is een generieke tekst zonder persoonsgegevens over software-architectuur."
    result = pii_anonymizer.anonymize_text(text, workflow="business_intelligence")
    assert result == text


@requires_presidio
def test_anonymize_text_pure_dutch_text_not_mangled_by_english_model():
    """Regressietest voor een echte bug (gevonden 2026-09-18): met beide
    taalmodellen blind op elke tekst losgelaten, herkende het Engelse model
    op zuiver Nederlandse tekst met hoge score (0.85) volledig onjuiste
    PERSON-entiteiten — bijv. "tien procent" en "vorig jaar" in de zin
    hieronder. Sindsdien beperkt _detect_confident_language() NER-detectie
    (PERSON/LOCATION) tot het taalmodel van de gedetecteerde dominante taal.
    """
    text = "De kwartaalomzet steeg dit jaar met tien procent ten opzichte van vorig jaar."
    result = pii_anonymizer.anonymize_text(text, workflow="business_intelligence")
    assert result == text


@requires_presidio
def test_anonymize_text_pure_dutch_text_still_detects_real_dutch_person():
    """Keerzijde van de vorige test: de taalbeperking mag de recall voor de
    daadwerkelijk gedetecteerde taal niet verlagen — een echte naam in
    zuiver Nederlandse tekst moet nog steeds worden herkend."""
    text = "Neem voor vragen contact op met Pieter de Vries, onze accountmanager."
    result = pii_anonymizer.anonymize_text(text, workflow="business_intelligence")
    assert "Pieter de Vries" not in result
    assert "<PERSOON>" in result
