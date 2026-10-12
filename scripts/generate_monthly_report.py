#!/usr/bin/env python3
"""Generate a per-tenant Valqeron monthly usage report PDF (NL or EN).

Usage:
  python scripts/generate_monthly_report.py --data <report.json> --lang nl|en --out <dir> \
      [--contact contact.json] [--next-steps <config>.json]

Talks to no network, no production token, no database — all the figures already live in the
--data JSON produced by scripts/monthly_report_data.py. Reuses the handout pipeline (same
design tokens, same headless-Chromium PDF step, same rendercheck) per the hand-off. Every
blocking check in tools/report/checks.py must pass or no PDF is left on disk.

See claude-code-handoff-batch-q-maandrapportage.md for the full design.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOUT_TOOL_DIR = REPO_ROOT / "tools" / "handout"
REPORT_TOOL_DIR = REPO_ROOT / "tools" / "report"
# Only tools/report/ goes on sys.path here — tools/handout/ also has a module named `checks`,
# so tools/report/checks.py itself loads the handout's checks.py/rendercheck.py via an explicit
# file path (importlib), not sys.path, and re-exports what this script needs from them.
sys.path.insert(0, str(REPORT_TOOL_DIR))
sys.path.insert(0, str(REPO_ROOT))

import fitz  # noqa: E402
import jinja2  # noqa: E402

from checks import check_contact_gate, check_pdf as rendercheck_pdf, is_concept_only, run_report_checks  # noqa: E402

TIER_DISPLAY = {"starter": "Starter", "business": "Business", "enterprise": "Enterprise"}

PERIOD_LABEL_NL = {
    1: "januari", 2: "februari", 3: "maart", 4: "april", 5: "mei", 6: "juni",
    7: "juli", 8: "augustus", 9: "september", 10: "oktober", 11: "november", 12: "december",
}
PERIOD_LABEL_EN = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}


def period_label(month: str, lang: str) -> str:
    year, m = (int(p) for p in month.split("-", 1))
    names = PERIOD_LABEL_NL if lang == "nl" else PERIOD_LABEL_EN
    return f"{names[m]} {year}"


def tenant_slug(name: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tenant"


def load_contact(path: Optional[Path]) -> Optional[dict]:
    if path and path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def load_next_steps(path: Optional[Path], lang: str) -> str:
    if not path or not path.exists():
        return (
            "Neem contact op voor een bespreking van deze cijfers."
            if lang == "nl"
            else "Contact us to discuss these figures."
        )
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    return config.get(lang, "") or config.get("text", "")


def build_context(data: dict, lang: str, contact: Optional[dict], next_steps_path: Optional[Path]) -> dict:
    concept_only = is_concept_only(contact)
    contact_text = None
    if not concept_only:
        # Same contact.json shape and template as the handout (tools/handout/handout/shared.yaml).
        template = (
            "Wie bel je? Eerste lijn is een supportverzoek via het portaal. Voor spoed: {urgent_phone}, "
            "{urgent_hours}. Beveiligings- of privacymelding: {security_contact}."
            if lang == "nl"
            else "Who do you call? First line is a support request through the portal. For urgent "
            "matters: {urgent_phone}, {urgent_hours}. For a security or privacy report: {security_contact}."
        )
        contact_text = template.format(**contact)

    return {
        "tenant_name": data["organization"]["name"],
        "tier_display": TIER_DISPLAY.get(data["organization"]["tier"] or "", data["organization"]["tier"] or "-"),
        "period_label": period_label(data["period"]["month"], lang),
        "generated_date": datetime.date.today().isoformat(),
        "concept_only": concept_only,
        "contact_text": contact_text,
        "runs_total": data["runs"]["total_this_month"],
        "runs_per_module": data["runs"]["per_module"],
        "documents": data["documents"],
        "support": data["support_requests"],
        "gov": data["governance"],
        "audit": data["audit"],
        "onboarding": data["onboarding"],
        "next_steps": load_next_steps(next_steps_path, lang),
    }


def render_html(context: dict, lang: str) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(REPORT_TOOL_DIR)), autoescape=True)
    template = env.get_template(f"template_{lang}.html")
    return template.render(**context)


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    script = HANDOUT_TOOL_DIR / "render_pdf.mjs"
    result = subprocess.run(
        ["node", str(script), str(html_path), str(pdf_path)],
        cwd=HANDOUT_TOOL_DIR, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"PDF rendering failed (exit {result.returncode})")


def extract_pdf_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--lang", required=True, choices=["nl", "en"])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--contact", type=Path, default=None)
    parser.add_argument("--next-steps", type=Path, default=None)
    args = parser.parse_args()

    args.out = args.out.resolve()
    args.data = args.data.resolve()
    if args.contact:
        args.contact = args.contact.resolve()
    if args.next_steps:
        args.next_steps = args.next_steps.resolve()

    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)
    json_text = json.dumps(data)

    contact = load_contact(args.contact)
    contact_warnings = check_contact_gate(contact)
    for w in contact_warnings:
        print(f"WARNING: {w} — rendering as a concept", file=sys.stderr)

    context = build_context(data, args.lang, contact, args.next_steps)
    html = render_html(context, args.lang)

    args.out.mkdir(parents=True, exist_ok=True)
    slug = tenant_slug(data["organization"]["name"])
    month = data["period"]["month"]
    base_name = f"Valqeron-Maandrapport_{slug}_{month}_{args.lang}"

    html_path = args.out / f"{base_name}.html"
    pdf_path = args.out / f"{base_name}.pdf"
    html_path.write_text(html, encoding="utf-8")

    try:
        html_to_pdf(html_path, pdf_path)
    finally:
        html_path.unlink(missing_ok=True)

    rendered_text = extract_pdf_text(pdf_path)
    problems = run_report_checks(rendered_text=rendered_text, json_text=json_text, lang=args.lang, contact=contact)
    if problems:
        pdf_path.unlink(missing_ok=True)
        print("BLOCKED — the following checks failed, no PDF was left on disk:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    render_problems = rendercheck_pdf(pdf_path)
    if render_problems:
        pdf_path.unlink(missing_ok=True)
        print("BLOCKED — rendercheck failed, no PDF was left on disk:", file=sys.stderr)
        for p in render_problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    concept_note = " (CONCEPT/DRAFT — contact.json missing or incomplete)" if context["concept_only"] else ""
    print(f"Wrote {pdf_path}{concept_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
