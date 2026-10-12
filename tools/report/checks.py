"""Blocking quality checks for the monthly report generator (Batch Q, Q3).

Reuses the handout pipeline wherever the hand-off says to ("gebruik de handout-pijplijn"):
the contact gate / concept-mode logic and the forbidden-word matcher come straight from
tools/handout/checks.py, and the PDF rendercheck comes straight from tools/handout/
rendercheck.py — nothing here reimplements those.

Checks specific to this report:
  1. forbidden words — the handout's own list, plus this hand-off's extra NL/EN phrases
  2. source attribution — every section's expected "Bron:"/"Source:" footnote is present
  3. no customer content — scans both the rendered PDF text and the data JSON for e-mail
     addresses, phone numbers, filenames and anonymisation-style <PLACEHOLDER> tokens
  4. period check — re-exported from scripts/monthly_report_data.py (already tested there)
  5. rendercheck — re-exported from tools/handout/rendercheck.py
  7. contact gate — re-exported from tools/handout/checks.py (check_contact_gate/is_concept_only)

"Steekproef" (spot-checking two figures against an independent manual count) is not a code
check — it is a manual step Claude Code performs against the real database and reports in the
hand-off's own "Rapport" section, same as every other batch in this project.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    """Loads a module from an explicit file path under a distinct name, bypassing sys.path —
    needed because tools/handout/checks.py and this file are both named `checks`, and a plain
    sys.path-based `import checks` would resolve ambiguously depending on insertion order."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_handout_checks = _load_module("_handout_checks", REPO_ROOT / "tools" / "handout" / "checks.py")
_handout_rendercheck = _load_module("_handout_rendercheck", REPO_ROOT / "tools" / "handout" / "rendercheck.py")
_report_data = _load_module("_monthly_report_data", REPO_ROOT / "scripts" / "monthly_report_data.py")

_HANDOUT_FORBIDDEN_EN = _handout_checks.FORBIDDEN_EN
_HANDOUT_FORBIDDEN_NL = _handout_checks.FORBIDDEN_NL
NEGATION_WORDS_EN = _handout_checks.NEGATION_WORDS_EN
NEGATION_WORDS_NL = _handout_checks.NEGATION_WORDS_NL
_boundary_pattern = _handout_checks._boundary_pattern
check_contact_gate = _handout_checks.check_contact_gate
is_concept_only = _handout_checks.is_concept_only

check_pdf = _handout_rendercheck.check_pdf  # re-exported
check_period_is_closed = _report_data.check_period_is_closed  # re-exported

# Extra phrases from this hand-off, on top of the handout's base list. Most overlap with words
# already in the base list (fully/automatic/guaranteed/certified/compliant) — kept anyway so the
# hand-off's own literal wording is directly, visibly enforced, not just implied by overlap.
REPORT_EXTRA_FORBIDDEN_NL = [
    "we monitoren continu",
    "alles veilig",
    "voldoet aan",
    "gegarandeerd",
    "volledig",
    "automatisch",
    "gecertificeerd",
    "ai-prestaties",
    "besparing",
]
REPORT_EXTRA_FORBIDDEN_EN = [
    "we continuously monitor",
    "everything is secure",
    "compliant with",
    "guaranteed",
    "fully",
    "automatic",
    "certified",
    "ai performance",
    "savings",
]

FORBIDDEN_NL = sorted(set(_HANDOUT_FORBIDDEN_NL) | set(REPORT_EXTRA_FORBIDDEN_NL))
FORBIDDEN_EN = sorted(set(_HANDOUT_FORBIDDEN_EN) | set(REPORT_EXTRA_FORBIDDEN_EN))


def check_forbidden_words_in_text(text: str, lang: str) -> List[str]:
    words = FORBIDDEN_NL if lang == "nl" else FORBIDDEN_EN
    negations = NEGATION_WORDS_NL if lang == "nl" else NEGATION_WORDS_EN
    lowered = text.lower()
    problems: List[str] = []
    for word in words:
        for m in _boundary_pattern(word).finditer(lowered):
            start = max(0, m.start() - 40)
            context = lowered[start:m.start()]
            if not any(neg in context for neg in negations):
                problems.append(f"forbidden word '{word}' without negation — ...{text[max(0, m.start()-30):m.end()+30]}...")
    return problems


REQUIRED_FOOTNOTES_NL = [
    "runs-register (telling per module, deze periode); governance-tabellen (huidige stand); auditlog-integriteitscontrole (opnamedatum)",
    "runs-register, documentregister, supportverzoeken-register, governance-tabellen",
    "runs-register, telling per actieve module, deze periode",
    "supportverzoeken-register, telling per status",
    "governance-tabellen (AI-systemen, risico's, incidenten, corrigerende maatregelen), stand op opnamedatum",
    "auditlog, telling per periode; integriteit via de hash-ketencontrole",
]
REQUIRED_FOOTNOTES_EN = [
    "runs register (count per module, this period); governance tables (current state); audit integrity check (as of generation date)",
    "runs register, document register, support requests register, governance tables",
    "runs register, count per active module, this period",
    "support requests register, count per status",
    "governance tables (AI systems, risks, incidents, corrective actions), state as of generation date",
    "audit log, count per period; integrity via the hash-chain check",
]


def _normalize_whitespace(text: str) -> str:
    """Collapses all whitespace (including PDF-extraction line breaks that land mid-sentence
    whenever a long footnote wraps across more than one visual line) into single spaces, so a
    continuous expected string can still be matched as a substring."""
    return " ".join(text.split())


def check_source_attribution(rendered_text: str, lang: str) -> List[str]:
    """Every section's expected footnote must be present. The footnotes are fixed template text
    (not derived per report), so this is a structural guard against a broken/truncated template,
    not a claim-by-claim scan like the handout's claim register. Both sides are whitespace-
    normalized first: PyMuPDF's get_text() inserts a newline at every visual line wrap, not just
    at paragraph breaks, so a long footnote that wraps across lines would otherwise never match
    an exact substring search."""
    required = REQUIRED_FOOTNOTES_NL if lang == "nl" else REQUIRED_FOOTNOTES_EN
    normalized = _normalize_whitespace(rendered_text)
    problems = []
    for footnote in required:
        if _normalize_whitespace(footnote) not in normalized:
            problems.append(f"missing expected source footnote: {footnote!r}")
    return problems


_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+31|0031|0)\s*6[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")
_FILENAME_RE = re.compile(r"\b[\w.-]+\.(?:txt|pdf|docx?|xlsx?|csv|png|jpe?g)\b", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"<[A-Z][A-Z_]*(?:_\d+)?>")


def check_no_customer_content(text: str, exclude_values: Iterable[str] = ()) -> List[str]:
    """Scans for e-mail/phone/filename/placeholder-shaped tokens. `exclude_values` are known,
    deliberately-included strings (Valqeron's own contact.json values — urgent_phone,
    security_contact) that must not trip this check: they are Valqeron's own published contact
    details, injected on purpose via the exact same contact.json mechanism the handout generator
    already uses, never customer data. Each excluded value is removed from the text before
    scanning, not merely permitted if found — so a customer e-mail that happens to differ from
    the configured contact address still breaks the build."""
    for value in exclude_values:
        if value:
            text = text.replace(value, "")

    problems: List[str] = []
    for label, pattern in (
        ("e-mail address", _EMAIL_RE),
        ("phone number", _PHONE_RE),
        ("filename", _FILENAME_RE),
        ("anonymisation placeholder", _PLACEHOLDER_RE),
    ):
        for m in pattern.finditer(text):
            problems.append(f"found a {label}-shaped token: {m.group(0)!r}")
    return problems


def run_report_checks(
    *, rendered_text: str, json_text: str, lang: str, contact: dict = None
) -> List[str]:
    """Runs every blocking check against the rendered report text and the data JSON text.
    Does NOT run the period check or the PDF rendercheck — those take different inputs (the
    collect() call, and a PDF path) and are run directly by the caller; both are re-exported
    from this module so a caller only needs to import tools/report/checks."""
    exclude = [contact.get(k) for k in ("urgent_phone", "security_contact")] if contact else []

    problems: List[str] = []
    problems += check_forbidden_words_in_text(rendered_text, lang)
    problems += check_source_attribution(rendered_text, lang)
    problems += check_no_customer_content(rendered_text, exclude_values=exclude)
    # the JSON data file never contains contact.json's values in the first place (Q1 collects
    # only counts/statuses), so no exclusion is needed there — a match there is always real.
    problems += check_no_customer_content(json_text)
    return problems
