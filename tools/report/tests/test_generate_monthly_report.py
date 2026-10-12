"""End-to-end tests for scripts/generate_monthly_report.py (Batch Q, Q2/Q3)."""
import json
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = str(REPO_ROOT / "venv" / "bin" / "python3")
SCRIPT = str(REPO_ROOT / "scripts" / "generate_monthly_report.py")


def _base_data(**overrides) -> dict:
    data = {
        "organization": {"id": 1, "name": "Test Tenant B.V.", "tier": "enterprise"},
        "period": {"month": "2026-09", "start": "2026-09-01T00:00:00", "end": "2026-10-01T00:00:00"},
        "generated_at": "2026-10-12T00:00:00Z",
        "runs": {
            "total_this_month": 5,
            "total_unmatched_module": 0,
            "per_module": [
                {"module_key": "customer_support_ai", "module_name": "Customer Support AI", "workflow_key": "customer_support", "ok": 4, "error": 1, "total": 5},
            ],
        },
        "documents": None,
        "support_requests": {"submitted_this_month": 0, "done_of_those": 0},
        "governance": {"open_incidents": 0, "open_corrective_actions": 0, "overdue_corrective_actions": 0, "ai_systems": 0, "ai_risks": 0},
        "audit": {"actions_this_month": 3, "chain_status": "valid"},
        "onboarding": None,
        "notes": {"degraded_not_counted": "see script docstring"},
    }
    data.update(overrides)
    return data


def _run(data: dict, tmp_path: Path, lang: str = "nl", contact: dict = None, next_steps: dict = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    data_path = tmp_path / "data.json"
    data_path.write_text(json.dumps(data), encoding="utf-8")
    out_dir = tmp_path / "out"

    args = [PYTHON, SCRIPT, "--data", str(data_path), "--lang", lang, "--out", str(out_dir)]

    if contact is not None:
        contact_path = tmp_path / "contact.json"
        contact_path.write_text(json.dumps(contact), encoding="utf-8")
        args += ["--contact", str(contact_path)]

    if next_steps is not None:
        ns_path = tmp_path / "next_steps.json"
        ns_path.write_text(json.dumps(next_steps), encoding="utf-8")
        args += ["--next-steps", str(ns_path)]

    result = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    return result, out_dir


def test_nl_concept_report_is_produced_without_contact(tmp_path):
    result, out_dir = _run(_base_data(), tmp_path, lang="nl")
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*_nl.pdf"))
    assert len(pdfs) == 1
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "CONCEPT" in full_text


def test_en_concept_report_is_produced_without_contact(tmp_path):
    result, out_dir = _run(_base_data(), tmp_path, lang="en")
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*_en.pdf"))
    assert len(pdfs) == 1
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "DRAFT" in full_text


def test_complete_contact_json_produces_a_non_concept_report_with_the_contact_shown(tmp_path):
    contact = {"urgent_phone": "+31 20 1234567", "urgent_hours": "Mon-Fri 09:00-17:00 CET", "security_contact": "security@valqeron.com"}
    result, out_dir = _run(_base_data(), tmp_path, lang="nl", contact=contact)
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "CONCEPT" not in full_text
    assert "security@valqeron.com" in full_text


def test_empty_month_zero_runs_still_produces_a_valid_report(tmp_path):
    data = _base_data(runs={"total_this_month": 0, "total_unmatched_module": 0, "per_module": []})
    result, out_dir = _run(data, tmp_path, lang="nl")
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "0" in full_text  # the zero shows up somewhere real (the runs-this-month KPI)


def test_documents_section_only_appears_when_the_module_is_active(tmp_path):
    data_without = _base_data(documents=None)
    result, out_dir = _run(data_without, tmp_path, lang="nl")
    doc = fitz.open(list(out_dir.glob("*.pdf"))[0])
    text_without = "\n".join(page.get_text() for page in doc)
    assert "Documenten" not in text_without

    data_with = _base_data(documents={"total": 9, "new_this_month": 2})
    result2, out_dir2 = _run(data_with, tmp_path / "with-docs", lang="nl")
    doc2 = fitz.open(list(out_dir2.glob("*.pdf"))[0])
    text_with = "\n".join(page.get_text() for page in doc2)
    assert "Documenten" in text_with
    assert "9 documenten totaal" in text_with


def test_onboarding_section_only_appears_when_a_project_is_active(tmp_path):
    data_without = _base_data(onboarding=None)
    result, out_dir = _run(data_without, tmp_path, lang="nl")
    doc = fitz.open(list(out_dir.glob("*.pdf"))[0])
    text_without = "\n".join(page.get_text() for page in doc)
    assert "Onboarding" not in text_without

    data_with = _base_data(onboarding={"phases": [{"phase": 1, "title": "Kickoff", "total": 3, "done": 2}]})
    result2, out_dir2 = _run(data_with, tmp_path / "with-onb", lang="nl")
    doc2 = fitz.open(list(out_dir2.glob("*.pdf"))[0])
    text_with = "\n".join(page.get_text() for page in doc2)
    assert "Onboarding" in text_with
    assert "Kickoff" in text_with


def test_a_forbidden_word_in_next_steps_config_blocks_the_build(tmp_path):
    next_steps = {"nl": "Dit is een gegarandeerd resultaat voor volgende maand."}
    result, out_dir = _run(_base_data(), tmp_path, lang="nl", next_steps=next_steps)
    assert result.returncode == 2
    assert "gegarandeerd" in result.stderr
    assert list(out_dir.glob("*.pdf")) == [] if out_dir.exists() else True


def test_a_leaked_placeholder_in_next_steps_blocks_the_build(tmp_path):
    next_steps = {"nl": "Zie <LOCATIE> voor meer details volgende maand."}
    result, out_dir = _run(_base_data(), tmp_path, lang="nl", next_steps=next_steps)
    assert result.returncode == 2
    assert "placeholder" in result.stderr


def test_default_next_steps_sentence_is_used_when_no_config_given(tmp_path):
    result, out_dir = _run(_base_data(), tmp_path, lang="nl")
    doc = fitz.open(list(out_dir.glob("*.pdf"))[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "Neem contact op voor een bespreking van deze cijfers" in full_text


def test_filename_follows_the_required_pattern(tmp_path):
    result, out_dir = _run(_base_data(organization={"id": 1, "name": "Acme Örg!", "tier": "starter"}), tmp_path, lang="nl")
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    assert len(pdfs) == 1
    name = pdfs[0].name
    assert name.startswith("Valqeron-Maandrapport_")
    assert "_2026-09_nl" in name


def test_no_html_file_is_left_behind(tmp_path):
    result, out_dir = _run(_base_data(), tmp_path, lang="nl")
    assert result.returncode == 0, result.stderr
    assert list(out_dir.glob("*.html")) == []


def test_relative_out_path_from_a_different_cwd_still_works(tmp_path):
    data_path = tmp_path / "data.json"
    data_path.write_text(json.dumps(_base_data()), encoding="utf-8")
    rel_out = "relative-out-dir"
    result = subprocess.run(
        [PYTHON, SCRIPT, "--data", str(data_path), "--lang", "nl", "--out", rel_out],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert len(list((tmp_path / rel_out).glob("*.pdf"))) == 1
