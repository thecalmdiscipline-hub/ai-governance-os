"""Tests for the PDF rendercheck (Batch M, M2's fourth quality control).

Builds small synthetic PDFs directly with PyMuPDF rather than going through the full
HTML/Jinja2/Chromium pipeline, so these stay fast and isolate the rendercheck logic itself.
"""
import sys
from pathlib import Path

import fitz
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rendercheck import check_pdf  # noqa: E402

A4_WIDTH, A4_HEIGHT = 595, 842  # points


@pytest.fixture
def tmp_pdf_path(tmp_path):
    return tmp_path / "test.pdf"


def _make_image(tmp_path: Path, color=(200, 160, 40)) -> Path:
    img_path = tmp_path / "shot.png"
    Image.new("RGB", (400, 200), color).save(img_path)
    return img_path


def test_blank_page_is_flagged(tmp_pdf_path):
    doc = fitz.open()
    doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    doc.save(tmp_pdf_path)
    problems = check_pdf(tmp_pdf_path)
    assert any("blank" in p for p in problems)


def test_page_with_body_text_is_not_blank(tmp_pdf_path):
    doc = fitz.open()
    page = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page.insert_text((50, 100), "A normal paragraph of body text.", fontsize=10)
    doc.save(tmp_pdf_path)
    problems = check_pdf(tmp_pdf_path)
    assert problems == []


def test_heading_stranded_at_bottom_of_page_is_flagged(tmp_pdf_path):
    doc = fitz.open()
    page = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page.insert_text((50, 100), "Some body text up top.", fontsize=10)
    # a heading-sized block right at the bottom margin, nothing after it
    page.insert_text((50, A4_HEIGHT - 40), "A stranded heading", fontsize=18)
    doc.save(tmp_pdf_path)
    problems = check_pdf(tmp_pdf_path)
    assert any("heading-sized" in p for p in problems)


def test_heading_at_top_of_page_is_not_flagged(tmp_pdf_path):
    doc = fitz.open()
    page = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page.insert_text((50, 100), "A heading up top", fontsize=18)
    page.insert_text((50, 140), "Followed by body text right after it.", fontsize=10)
    doc.save(tmp_pdf_path)
    problems = check_pdf(tmp_pdf_path)
    assert problems == []


def test_image_without_a_caption_below_it_is_flagged(tmp_path, tmp_pdf_path):
    img_path = _make_image(tmp_path)
    doc = fitz.open()
    page = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page.insert_text((50, 100), "Some intro text.", fontsize=10)
    page.insert_image(fitz.Rect(50, 150, 450, 350), filename=str(img_path))
    # no caption text below the image at all
    doc.save(tmp_pdf_path)
    problems = check_pdf(tmp_pdf_path)
    assert any("no caption" in p for p in problems)


def test_image_with_a_caption_directly_below_it_is_not_flagged(tmp_path, tmp_pdf_path):
    img_path = _make_image(tmp_path)
    doc = fitz.open()
    page = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page.insert_text((50, 100), "Some intro text.", fontsize=10)
    page.insert_image(fitz.Rect(50, 150, 450, 350), filename=str(img_path))
    page.insert_text((50, 360), "Figure 1: the screenshot caption.", fontsize=8.5)
    doc.save(tmp_pdf_path)
    problems = check_pdf(tmp_pdf_path)
    assert problems == []


def test_image_with_caption_pushed_to_the_next_page_is_flagged(tmp_path, tmp_pdf_path):
    img_path = _make_image(tmp_path)
    doc = fitz.open()
    page1 = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page1.insert_text((50, 100), "Some intro text.", fontsize=10)
    # image right at the very bottom of the page, caption would land on page 2
    page1.insert_image(fitz.Rect(50, A4_HEIGHT - 100, 450, A4_HEIGHT - 10), filename=str(img_path))
    page2 = doc.new_page(width=A4_WIDTH, height=A4_HEIGHT)
    page2.insert_text((50, 50), "Caption that landed on the wrong page.", fontsize=8.5)
    doc.save(tmp_pdf_path)
    problems = check_pdf(tmp_pdf_path)
    assert any("no caption" in p and "page 1" in p for p in problems)


def test_real_generated_concept_pdf_passes_rendercheck(tmp_path):
    """Integration smoke test: generate a real NL concept handout via the actual
    scripts/generate_handout.py pipeline and rendercheck the result."""
    import json
    import subprocess

    repo_root = Path(__file__).resolve().parents[3]
    config = {
        "tenant_name": "Rendercheck Smoke Test",
        "tier": "starter",
        "modules": ["core", "customer_support_ai"],
        "language": "nl",
        "confirmed_blocks": [],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    out_dir = tmp_path / "out"

    result = subprocess.run(
        [
            str(repo_root / "venv" / "bin" / "python3"),
            str(repo_root / "scripts" / "generate_handout.py"),
            "--config", str(config_path),
            "--out", str(out_dir),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr

    pdfs = list(out_dir.glob("*.pdf"))
    assert len(pdfs) == 1
    assert "CONCEPT" in result.stdout

    problems = check_pdf(pdfs[0])
    assert problems == [], problems
