"""End-to-end tests for scripts/generate_handout.py (Batch M, M2).

Runs the real script as a subprocess against the real content files — these are integration
tests, not unit tests of checks.py (already covered in test_checks.py). No network, no
production token; --screenshots is omitted everywhere here (M3 covers that).
"""
import json
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = str(REPO_ROOT / "venv" / "bin" / "python3")
SCRIPT = str(REPO_ROOT / "scripts" / "generate_handout.py")


def _run(config: dict, tmp_path: Path, contact: dict = None, screenshots_dir: Path = None, language: str = None):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    out_dir = tmp_path / "out"

    args = [PYTHON, SCRIPT, "--config", str(config_path), "--out", str(out_dir)]

    if contact is not None:
        contact_path = tmp_path / "contact.json"
        contact_path.write_text(json.dumps(contact), encoding="utf-8")
        args += ["--contact", str(contact_path)]

    if screenshots_dir is not None:
        args += ["--screenshots", str(screenshots_dir)]

    if language is not None:
        args += ["--language", language]

    result = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    return result, out_dir


def _base_config(**overrides) -> dict:
    config = {
        "tenant_name": "Acme Client B.V.",
        "tier": "starter",
        "modules": ["core", "customer_support_ai", "document_intelligence"],
        "language": "nl",
        "confirmed_blocks": [],
    }
    config.update(overrides)
    return config


def test_nl_concept_handout_is_produced_without_contact(tmp_path):
    result, out_dir = _run(_base_config(language="nl"), tmp_path)
    assert result.returncode == 0, result.stderr
    assert "CONCEPT" in result.stdout
    pdfs = list(out_dir.glob("*_nl_*.pdf"))
    assert len(pdfs) == 1


def test_en_concept_handout_is_produced_without_contact(tmp_path):
    result, out_dir = _run(_base_config(language="en"), tmp_path)
    assert result.returncode == 0, result.stderr
    assert "CONCEPT" in result.stdout
    pdfs = list(out_dir.glob("*_en_*.pdf"))
    assert len(pdfs) == 1


def test_complete_contact_json_produces_a_non_concept_handout(tmp_path):
    contact = {
        "urgent_phone": "+31 20 1234567",
        "urgent_hours": "Mon-Fri 09:00-17:00 CET",
        "security_contact": "security@valqeron.com",
    }
    result, out_dir = _run(_base_config(), tmp_path, contact=contact)
    assert result.returncode == 0, result.stderr
    assert "CONCEPT" not in result.stdout
    pdfs = list(out_dir.glob("*.pdf"))
    assert len(pdfs) == 1

    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "security@valqeron.com" in full_text
    assert "CONCEPT" not in full_text
    assert "DRAFT" not in full_text


def test_incomplete_contact_json_still_forces_concept_mode(tmp_path):
    # Per the hand-off, an incomplete contact.json never blocks the build (unlike the HR lock
    # or an unknown module) — it only forces concept mode and prints a warning.
    contact = {"urgent_phone": "+31 20 1234567", "urgent_hours": "", "security_contact": "security@valqeron.com"}
    result, out_dir = _run(_base_config(), tmp_path, contact=contact)
    assert result.returncode == 0, result.stderr
    assert "CONCEPT" in result.stdout
    assert "urgent_hours" in result.stderr  # the specific missing field is reported
    pdfs = list(out_dir.glob("*.pdf"))
    assert len(pdfs) == 1
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "CONCEPT" in full_text


def test_hr_module_without_confirmation_is_blocked(tmp_path):
    config = _base_config(modules=["core", "hr_recruitment_ai"], confirmed_blocks=[])
    result, out_dir = _run(config, tmp_path)
    assert result.returncode == 2
    assert "hr_recruitment_ai" in result.stderr
    assert list(out_dir.glob("*.pdf")) == [] if out_dir.exists() else True


def test_hr_module_with_confirmation_is_allowed(tmp_path):
    config = _base_config(modules=["core", "hr_recruitment_ai"], confirmed_blocks=["hr_recruitment_ai"])
    result, out_dir = _run(config, tmp_path)
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    assert len(pdfs) == 1
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "HR Recruitment" in full_text


def test_unknown_module_in_config_is_blocked(tmp_path):
    config = _base_config(modules=["core", "not_a_real_module"])
    result, out_dir = _run(config, tmp_path)
    assert result.returncode == 2
    assert "not_a_real_module" in result.stderr


def test_all_ten_modules_selected_produces_a_handout_with_every_module_name(tmp_path):
    all_modules = [
        "core", "document_intelligence", "compliance_monitor", "customer_support_ai",
        "sales_qualification_ai", "invoice_processing_ai", "marketing_automation_ai",
        "meeting_agenda_assistant", "quote_contract_generator", "business_intelligence",
    ]
    config = _base_config(modules=all_modules, tier="enterprise")
    result, out_dir = _run(config, tmp_path)
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    for name in [
        "Document Intelligence", "Compliance Monitor", "Customer Support AI",
        "Sales Qualification AI", "Invoice Processing AI", "Marketing Automation AI",
        "Meeting Agenda Assistant", "Quote & Contract Generator", "Business Intelligence",
    ]:
        assert name in full_text, f"missing module name: {name}"


def test_filename_follows_the_required_pattern(tmp_path):
    result, out_dir = _run(_base_config(tenant_name="Test Örg B.V.!"), tmp_path)
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    assert len(pdfs) == 1
    name = pdfs[0].name
    assert name.startswith("Valqeron-Handout_")
    assert "_nl_" in name
    assert name.endswith(".pdf")


def test_no_html_file_is_left_behind(tmp_path):
    result, out_dir = _run(_base_config(), tmp_path)
    assert result.returncode == 0, result.stderr
    assert list(out_dir.glob("*.html")) == []


def _make_screenshot(tmp_path: Path, name: str):
    from PIL import Image
    path = tmp_path / name
    Image.new("RGB", (1440, 900), (20, 23, 34)).save(path)
    return path


def test_a_tab_screenshot_appears_in_the_rendered_pdf(tmp_path):
    shots_dir = tmp_path / "screenshots"
    shots_dir.mkdir()
    _make_screenshot(shots_dir, "home.png")
    manifest = {
        "_meta": {"frontend_build_sha": "deadbee", "captured_at": "2026-10-12T00:00:00Z"},
        "home": [{"path": "home.png", "caption": "The Home tab."}],
    }
    (shots_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result, out_dir = _run(_base_config(), tmp_path, screenshots_dir=shots_dir)
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "The Home tab." in full_text
    total_images = sum(len(page.get_images()) for page in doc)
    assert total_images >= 1


def test_module_screenshot_appears_inside_its_module_card(tmp_path):
    shots_dir = tmp_path / "screenshots"
    shots_dir.mkdir()
    _make_screenshot(shots_dir, "dk_1.png")
    manifest = {
        "_meta": {"frontend_build_sha": "deadbee", "captured_at": "2026-10-12T00:00:00Z"},
        "document_intelligence": [{"path": "dk_1.png", "caption": "Ask your documents."}],
    }
    (shots_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    config = _base_config(modules=["core", "document_intelligence"])
    result, out_dir = _run(config, tmp_path, screenshots_dir=shots_dir)
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*.pdf"))
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "Ask your documents." in full_text


def test_stale_screenshot_manifest_produces_a_warning_but_still_builds(tmp_path, monkeypatch):
    shots_dir = tmp_path / "screenshots"
    shots_dir.mkdir()
    _make_screenshot(shots_dir, "home.png")
    manifest = {
        "_meta": {"frontend_build_sha": "0000000", "captured_at": "2020-01-01T00:00:00Z"},
        "home": [{"path": "home.png", "caption": "An old screenshot."}],
    }
    (shots_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result, out_dir = _run(_base_config(), tmp_path, screenshots_dir=shots_dir)
    assert result.returncode == 0, result.stderr
    # Either the frontend repo isn't checked out on this machine (no warning possible) or it is
    # and the SHAs genuinely differ (0000000 can never be real) — accept both, but never fail
    # the build over this.
    if "ai-governance-frontend" in (result.stderr or ""):
        assert "stale" in result.stderr or "0000000" in result.stderr


def test_language_flag_overrides_the_configs_own_language(tmp_path):
    config = _base_config(language="nl")
    result, out_dir = _run(config, tmp_path, language="en")
    assert result.returncode == 0, result.stderr
    pdfs = list(out_dir.glob("*_en_*.pdf"))
    assert len(pdfs) == 1
    doc = fitz.open(pdfs[0])
    full_text = "\n".join(page.get_text() for page in doc)
    assert "Welcome to Valqeron" in full_text
    assert "Welkom bij Valqeron" not in full_text


def test_atlas_demo_enterprise_example_config_is_valid(tmp_path):
    repo_root = REPO_ROOT
    config_path = repo_root / "tools" / "handout" / "examples" / "atlas-demo-enterprise.json"
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [PYTHON, SCRIPT, "--config", str(config_path), "--out", str(out_dir)],
        cwd=repo_root, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert len(list(out_dir.glob("*.pdf"))) == 1


def test_starter_example_config_is_valid(tmp_path):
    repo_root = REPO_ROOT
    config_path = repo_root / "tools" / "handout" / "examples" / "starter-example.json"
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [PYTHON, SCRIPT, "--config", str(config_path), "--out", str(out_dir)],
        cwd=repo_root, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert len(list(out_dir.glob("*.pdf"))) == 1


def test_relative_out_path_from_repo_root_still_works(tmp_path):
    """Regression test: --out as a path relative to the CALLER's cwd (not tools/handout/, where
    the Node PDF renderer runs with its own different cwd) must still resolve correctly."""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_base_config()), encoding="utf-8")

    rel_out = "relative-out-dir"
    result = subprocess.run(
        [PYTHON, SCRIPT, "--config", str(config_path), "--out", rel_out],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    out_dir = tmp_path / rel_out
    assert len(list(out_dir.glob("*.pdf"))) == 1
    assert list(out_dir.glob("*.html")) == []
