"""The fourth blocking quality control for the handout generator (M2): render every page to
check it actually looks right, not just that the checks.py text rules passed.

Checks, per page:
  - not blank (some text or image content)
  - no heading-sized text block sitting as the very last block near the bottom margin
    (a heading stranded at the end of a page, its body pushed to the next one)
  - every image has a caption-sized text block directly below it on the SAME page (a
    screenshot never separated from its caption)

This needs PyMuPDF (fitz), already used elsewhere in this repo's demo productions. It is a
read-only inspection of an already-rendered PDF — no network, no portal access.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import fitz  # PyMuPDF

_BOTTOM_MARGIN_PT = 20 * 72 / 25.4  # 20mm in points, matches the @page margin in the template
_HEADING_MIN_SIZE = 11.0  # pt — h3 is 11.5pt, so anything at/above this is heading-sized
_CAPTION_MAX_GAP_PT = 30  # how far below an image a caption may start and still "belong" to it


def _page_is_blank(page: fitz.Page) -> bool:
    text = page.get_text().strip()
    images = page.get_images()
    return not text and not images


def _last_block_is_a_stranded_heading(page: fitz.Page) -> bool:
    blocks = [b for b in page.get_text("dict")["blocks"] if b.get("lines")]
    if not blocks:
        return False
    page_h = page.rect.height
    last = blocks[-1]
    # a block near the bottom of the page
    if last["bbox"][1] < page_h - _BOTTOM_MARGIN_PT - 40:
        return False
    sizes = [span["size"] for line in last["lines"] for span in line["spans"]]
    if not sizes:
        return False
    return max(sizes) >= _HEADING_MIN_SIZE


def _images_have_captions(page: fitz.Page) -> List[str]:
    problems: List[str] = []
    images_on_page = page.get_image_info()
    if not images_on_page:
        return problems

    text_blocks = [b for b in page.get_text("dict")["blocks"] if b.get("lines")]

    for img in images_on_page:
        img_bottom = img["bbox"][3]
        img_left, img_right = img["bbox"][0], img["bbox"][2]
        has_caption_below = False
        for b in text_blocks:
            bx0, by0, bx1, by1 = b["bbox"]
            vertically_close = 0 <= (by0 - img_bottom) <= _CAPTION_MAX_GAP_PT
            horizontally_overlaps = bx0 < img_right and bx1 > img_left
            if vertically_close and horizontally_overlaps:
                has_caption_below = True
                break
        if not has_caption_below:
            problems.append(f"image at {img['bbox']} has no caption-like text directly below it on the same page")

    return problems


def check_pdf(pdf_path: Path) -> List[str]:
    problems: List[str] = []
    doc = fitz.open(pdf_path)

    if doc.page_count == 0:
        return ["PDF has zero pages"]

    for i, page in enumerate(doc):
        page_label = f"page {i + 1}"
        if _page_is_blank(page):
            problems.append(f"{page_label}: blank (no text, no images)")
            continue
        if _last_block_is_a_stranded_heading(page):
            problems.append(f"{page_label}: a heading-sized text block is the last thing on the page")
        for p in _images_have_captions(page):
            problems.append(f"{page_label}: {p}")

    doc.close()
    return problems


def main() -> int:
    import sys

    if len(sys.argv) != 2:
        print("Usage: python rendercheck.py <pdf-path>")
        return 2
    problems = check_pdf(Path(sys.argv[1]))
    if problems:
        print(f"RENDERCHECK PROBLEMS ({len(problems)}):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("RENDERCHECK OK: no blank pages, no stranded headings, no uncaptioned screenshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
