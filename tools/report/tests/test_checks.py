"""Tests for tools/report/checks.py (Batch Q, Q3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checks import (  # noqa: E402
    check_forbidden_words_in_text,
    check_no_customer_content,
    check_source_attribution,
    is_concept_only,
    run_report_checks,
)


# ---------- forbidden words: base handout list still enforced ----------

def test_handout_forbidden_word_still_flagged_without_negation():
    problems = check_forbidden_words_in_text("This is guaranteed to work.", "en")
    assert any("guarantee" in p for p in problems)


def test_handout_forbidden_word_allowed_when_negated():
    assert check_forbidden_words_in_text("This is not guaranteed.", "en") == []


# ---------- forbidden words: the report's own extra phrases ----------

def test_report_specific_nl_phrase_is_flagged():
    problems = check_forbidden_words_in_text("We monitoren continu de omgeving.", "nl")
    assert any("we monitoren continu" in p for p in problems)


def test_report_specific_en_savings_claim_is_flagged():
    problems = check_forbidden_words_in_text("This results in real savings for you.", "en")
    assert any("savings" in p for p in problems)


def test_ai_performance_phrase_is_flagged():
    problems = check_forbidden_words_in_text("AI-prestaties zijn dit kwartaal verbeterd.", "nl")
    assert any("ai-prestaties" in p for p in problems)


def test_everything_secure_phrase_is_flagged():
    problems = check_forbidden_words_in_text("Alles veilig deze maand.", "nl")
    assert any("alles veilig" in p for p in problems)


# ---------- source attribution ----------

def test_missing_footnote_is_flagged():
    problems = check_source_attribution("Some report text without any footnotes at all.", "nl")
    assert len(problems) > 0


def test_all_present_footnotes_pass_even_when_line_wrapped():
    # Simulates PyMuPDF inserting a newline mid-sentence where a long footnote wraps visually.
    text = (
        "Bron: runs-register (telling per module, deze periode); governance-tabellen\n"
        "(huidige stand); auditlog-integriteitscontrole (opnamedatum).\n"
        "Bron: runs-register, documentregister, supportverzoeken-register, governance-tabellen\n"
        "Bron: runs-register, telling per actieve module, deze periode\n"
        "Bron: supportverzoeken-register, telling per status\n"
        "Bron: governance-tabellen (AI-systemen, risico's, incidenten, corrigerende maatregelen), stand op opnamedatum\n"
        "Bron: auditlog, telling per periode; integriteit via de hash-ketencontrole\n"
    )
    assert check_source_attribution(text, "nl") == []


def test_footnotes_are_language_specific():
    # An NL footnote must not satisfy the EN requirement.
    nl_text = "Bron: runs-register (telling per module, deze periode); governance-tabellen (huidige stand); auditlog-integriteitscontrole (opnamedatum)."
    problems = check_source_attribution(nl_text, "en")
    assert len(problems) > 0


# ---------- no customer content ----------

def test_email_address_is_flagged():
    problems = check_no_customer_content("Contact jan.devries@acme.nl for details.")
    assert any("e-mail" in p for p in problems)


def test_nl_phone_number_is_flagged():
    problems = check_no_customer_content("Bel 06-12345678 voor meer informatie.")
    assert any("phone" in p for p in problems)


def test_filename_is_flagged():
    problems = check_no_customer_content("See invoice-2026-09.pdf for the original.")
    assert any("filename" in p for p in problems)


def test_anonymization_placeholder_is_flagged():
    problems = check_no_customer_content("The client is <PERSOON_2> and lives in <LOCATIE>.")
    assert len(problems) == 2


def test_clean_text_has_no_problems():
    assert check_no_customer_content("15 runs this month, 2 open incidents, 1 overdue action.") == []


def test_known_contact_values_are_excluded_from_the_scan():
    text = "For urgent matters: +31 20 1234567. Security: security@valqeron.com."
    problems = check_no_customer_content(
        text, exclude_values=["+31 20 1234567", "security@valqeron.com"]
    )
    assert problems == []


def test_an_email_that_is_not_the_configured_contact_still_breaks_the_build():
    text = "For urgent matters: +31 20 1234567. Contact jan@customer-company.nl."
    problems = check_no_customer_content(text, exclude_values=["+31 20 1234567", "security@valqeron.com"])
    assert any("jan@customer-company.nl" in p for p in problems)


# ---------- run_report_checks: integration ----------

def test_run_report_checks_combines_all_checks_and_respects_contact_exclusion():
    rendered = (
        "Bron: runs-register (telling per module, deze periode); governance-tabellen "
        "(huidige stand); auditlog-integriteitscontrole (opnamedatum). "
        "Bron: runs-register, documentregister, supportverzoeken-register, governance-tabellen "
        "Bron: runs-register, telling per actieve module, deze periode "
        "Bron: supportverzoeken-register, telling per status "
        "Bron: governance-tabellen (AI-systemen, risico's, incidenten, corrigerende maatregelen), stand op opnamedatum "
        "Bron: auditlog, telling per periode; integriteit via de hash-ketencontrole "
        "Voor spoed: security@valqeron.com."
    )
    contact = {"urgent_phone": "+31 20 1234567", "security_contact": "security@valqeron.com"}
    problems = run_report_checks(rendered_text=rendered, json_text="{}", lang="nl", contact=contact)
    assert problems == []


def test_run_report_checks_flags_a_forbidden_word_even_with_contact_present():
    rendered = "Dit is gegarandeerd correct. Voor spoed: security@valqeron.com."
    contact = {"urgent_phone": "+31 20 1234567", "security_contact": "security@valqeron.com"}
    problems = run_report_checks(rendered_text=rendered, json_text="{}", lang="nl", contact=contact)
    assert any("gegarandeerd" in p for p in problems)


# ---------- re-exported handout helpers still work ----------

def test_is_concept_only_reexport_works():
    assert is_concept_only(None) is True
    assert is_concept_only({"urgent_phone": "x", "urgent_hours": "y", "security_contact": "z"}) is False
