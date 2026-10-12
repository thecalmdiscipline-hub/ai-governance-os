#!/usr/bin/env python3
"""Generate a per-tenant Valqeron client handout PDF (NL or EN).

Usage:
  python scripts/generate_handout.py --config <klant>.json [--contact contact.json] \
      --out <dir> [--screenshots <dir>]

Talks to no network and no production token. Input is one config JSON (tenant_name, tier,
modules, language, generated_for, confirmed_blocks) and, optionally, a contact.json (see
tools/handout/handout/shared.yaml's `contact` block) and a screenshot manifest produced by
tools/handout/capture_screenshots.py. Renders the handout via Jinja2 + a headless-Chromium PDF
step (tools/handout/render_pdf.mjs, playwright-core) and refuses to write a PDF if any of the
four blocking checks in tools/handout/checks.py fails.

See claude-code-handoff-batch-m-handout-generator.md for the full design.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOUT_TOOL_DIR = REPO_ROOT / "tools" / "handout"
sys.path.insert(0, str(HANDOUT_TOOL_DIR))
sys.path.insert(0, str(REPO_ROOT))

import jinja2  # noqa: E402

from checks import check_contact_gate, is_concept_only, load_content, run_all_checks  # noqa: E402
from app.services.module_access import BASE_MODULES  # noqa: E402

TEMPLATE_VERSION = "1.0.0"

COPY: Dict[str, Dict[str, str]] = {
    "nl": {
        "tier_label": "Tier",
        "date_label": "Datum",
        "language_label": "Taal",
        "version_label": "Versie",
        "welcome_eyebrow": "WELKOM",
        "welcome_title": "Welkom bij Valqeron",
        "login_heading": "Inloggen",
        "change_password_heading": "Wachtwoord wijzigen",
        "mfa_heading": "Tweestapsverificatie",
        "tabs_heading": "De tabs in het portaal",
        "tab_col": "Tab",
        "what_col": "Wat je er vindt",
        "progress_heading": "Voortgang van jullie onboarding",
        "support_heading": "Hulp en support",
        "expect_heading": "Wat je mag verwachten",
        "modules_eyebrow": "PRODUCTEN",
        "modules_title": "De workflows in jullie omgeving",
        "does_label": "Wat het doet",
        "sees_label": "Wat je ziet",
        "you_do_label": "Wat je zelf doet",
        "human_label": "Wat een mens controleert",
        "not_yet_label": "Wat nog niet kan",
        "contact_eyebrow": "CONTACT",
        "contact_title": "Wie bel je?",
    },
    "en": {
        "tier_label": "Tier",
        "date_label": "Date",
        "language_label": "Language",
        "version_label": "Version",
        "welcome_eyebrow": "WELCOME",
        "welcome_title": "Welcome to Valqeron",
        "login_heading": "Signing in",
        "change_password_heading": "Changing your password",
        "mfa_heading": "Two-step verification",
        "tabs_heading": "The tabs in the portal",
        "tab_col": "Tab",
        "what_col": "What you will find there",
        "progress_heading": "Your onboarding progress",
        "support_heading": "Help and support",
        "expect_heading": "What you can expect",
        "modules_eyebrow": "PRODUCTS",
        "modules_title": "The workflows in your environment",
        "does_label": "What it does",
        "sees_label": "What you see",
        "you_do_label": "What you do",
        "human_label": "What a human checks",
        "not_yet_label": "What is not possible yet",
        "contact_eyebrow": "CONTACT",
        "contact_title": "Who do you call?",
    },
}

TIER_DISPLAY = {"starter": "Starter", "business": "Business", "enterprise": "Enterprise"}
LANGUAGE_DISPLAY = {"nl": "Nederlands", "en": "English"}

NOT_YET_NO_FORM = {
    "nl": "Voor deze workflow is in het portaal nog geen startformulier; Valqeron richt het gebruik op aanvraag voor je in.",
    "en": "This workflow does not have a start form in the portal yet; Valqeron sets up its use for you on request.",
}
NOT_YET_NO_APPROVAL = {
    "nl": "Er is geen ingebouwde goedkeuringsstap.",
    "en": "There is no built-in approval step.",
}


def tenant_slug(tenant_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", tenant_name.lower()).strip("-")
    return slug or "tenant"


def frontend_head_sha(frontend_repo: Path = Path.home() / "ai-governance-frontend") -> Optional[str]:
    """The ai-governance-frontend repo's current HEAD, used as a freshness reference for
    screenshot manifests. CD auto-deploys every green push to main, so local HEAD is the best
    available proxy for 'what is live' without a network call. Returns None if that repo isn't
    checked out on this machine (the freshness check is then skipped, not failed)."""
    if not frontend_repo.is_dir():
        return None
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h"],
            cwd=frontend_repo, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def check_screenshot_freshness(screenshots_dir: Optional[Path]) -> List[str]:
    """Non-blocking: warns if the screenshot manifest's frontend_build_sha predates the local
    ai-governance-frontend repo's current HEAD (per the hand-off: warn, never break silently)."""
    if not screenshots_dir:
        return []
    manifest_path = screenshots_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        raw = json.load(f)
    manifest_sha = raw.get("_meta", {}).get("frontend_build_sha")
    current_sha = frontend_head_sha()
    if manifest_sha and current_sha and manifest_sha != current_sha:
        return [
            f"screenshots were captured at frontend commit {manifest_sha}, but "
            f"ai-governance-frontend's current HEAD is {current_sha} — screens may be stale"
        ]
    return []


def claude_md_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", "CLAUDE.md"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        sha = out.stdout.strip()
        return sha or "unknown"
    except Exception:
        return "unknown"


def build_not_yet(has_start_form: bool, language: str) -> str:
    parts = []
    if not has_start_form:
        parts.append(NOT_YET_NO_FORM[language])
    parts.append(NOT_YET_NO_APPROVAL[language])
    return " ".join(parts)


def load_screenshots_manifest(screenshots_dir: Optional[Path]) -> dict:
    """Loads manifest.json and resolves every shot's `path` to an absolute file:// URI, so the
    <img> tag works regardless of where the intermediate HTML file ends up relative to the
    screenshots directory (Chromium's file:// scheme does not require same-directory images)."""
    if not screenshots_dir:
        return {}
    manifest_path = screenshots_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    with open(manifest_path, encoding="utf-8") as f:
        raw = json.load(f)

    resolved = {}
    for key, shots in raw.items():
        if key == "_meta":
            continue
        resolved[key] = [
            {**shot, "path": (screenshots_dir / shot["path"]).resolve().as_uri()}
            for shot in shots
        ]
    return resolved


def resolve_modules(config_modules: List[str], modules_yaml: dict, language: str, screenshots: dict) -> List[dict]:
    by_key = {m["key"]: m for m in modules_yaml.get("modules", [])}
    base_by_key = {m["key"]: m for m in BASE_MODULES}

    out = []
    for key in config_modules:
        if key == "core":
            continue
        entry = by_key[key]
        base = base_by_key[key]
        has_start_form = bool(entry.get("has_start_form", False))

        def block_text(section: str) -> Optional[str]:
            b = entry.get(section)
            if not b:
                return None
            return b.get(language)

        module_shots = screenshots.get(key, [])

        out.append({
            "key": key,
            "name": base["name"],
            "does": block_text("does"),
            "sees": block_text("sees"),
            "you_do": block_text("you_do"),
            "human": block_text("human"),
            "extra_note": block_text("extra_note"),
            "tier_note": block_text("tier_note"),
            "not_yet": build_not_yet(has_start_form, language),
            "screenshots": module_shots,
        })
    return out


def resolve_tabs(shared_yaml: dict, language: str) -> List[dict]:
    label_map = {
        "home": {"nl": "Home", "en": "Home"},
        "core": {"nl": "Core", "en": "Core"},
        "products": {"nl": "Products", "en": "Products"},
        "results": {"nl": "Results", "en": "Results"},
        "documents": {"nl": "Documents", "en": "Documents"},
        "governance": {"nl": "Governance", "en": "Governance"},
        "account": {"nl": "Account", "en": "Account"},
    }
    out = []
    for tab in shared_yaml.get("tabs", []):
        out.append({
            "label": label_map.get(tab["key"], {}).get(language, tab["key"]),
            "text": tab.get(language, ""),
        })
    return out


def build_context(config: dict, contact: Optional[dict], content: dict, screenshots_dir: Optional[Path]) -> dict:
    language = config["language"]
    copy = COPY[language]
    shared_yaml = content["shared"]
    modules_yaml = content["modules"]

    shared_text = {bid: block.get(language, "") for bid, block in shared_yaml.get("blocks", {}).items() if bid != "contact"}

    concept_only = is_concept_only(contact)
    if concept_only:
        contact_text = None
    else:
        template_key = "nl_template" if language == "nl" else "en_template"
        contact_text = shared_yaml["blocks"]["contact"][template_key].format(**contact)

    screenshots = load_screenshots_manifest(screenshots_dir)
    modules = resolve_modules(config["modules"], modules_yaml, language, screenshots)
    tabs = resolve_tabs(shared_yaml, language)

    tab_order = ["home", "core", "products", "results", "documents", "governance", "account"]
    tab_screenshots = [shot for key in tab_order for shot in screenshots.get(key, [])]

    module_intro = modules_yaml.get("core", {}).get(language, "")

    return {
        "copy": copy,
        "language": language,
        "language_display": LANGUAGE_DISPLAY[language],
        "tenant_name": config["tenant_name"],
        "tier_display": TIER_DISPLAY.get(config.get("tier", ""), config.get("tier", "")),
        "generated_date": datetime.date.today().isoformat(),
        "template_version": TEMPLATE_VERSION,
        "claude_md_sha": claude_md_sha(),
        "shared": shared_text,
        "tabs": tabs,
        "tab_screenshots": tab_screenshots,
        "modules": modules,
        "module_intro": module_intro,
        "concept_only": concept_only,
        "contact_text": contact_text,
    }


def render_html(context: dict) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(HANDOUT_TOOL_DIR)),
        autoescape=True,
    )
    template = env.get_template("template.html.jinja")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--contact", type=Path, default=None)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--screenshots", type=Path, default=None)
    parser.add_argument("--language", choices=["nl", "en"], default=None, help="Overrides the config's own language field, so one config can produce both PDFs.")
    args = parser.parse_args()
    # Resolve to absolute paths up front: html_to_pdf() runs the Node renderer with its cwd set
    # to tools/handout/ (so it finds its own node_modules), so a relative --out/--screenshots
    # path given on this script's own (different) cwd must not be left relative, or the
    # renderer would resolve it against the wrong directory and fail with ERR_FILE_NOT_FOUND.
    args.out = args.out.resolve()
    if args.screenshots:
        args.screenshots = args.screenshots.resolve()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    if args.language:
        config["language"] = args.language

    contact = None
    if args.contact and args.contact.exists():
        with open(args.contact, encoding="utf-8") as f:
            contact = json.load(f)

    content = load_content()
    catalog_keys = {m["key"] for m in content["modules"]["modules"]}
    selected = set(config["modules"])
    confirmed = set(config.get("confirmed_blocks", []))

    problems = run_all_checks(
        content=content,
        selected_module_keys=selected,
        confirmed_blocks=confirmed,
        contact_data=contact,
        catalog_module_keys=catalog_keys,
    )
    if problems:
        print("BLOCKED — the following checks failed, no PDF was produced:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    contact_warnings = check_contact_gate(contact)
    for w in contact_warnings:
        print(f"WARNING: {w} — rendering as a concept", file=sys.stderr)

    for w in check_screenshot_freshness(args.screenshots):
        print(f"WARNING: {w}", file=sys.stderr)

    context = build_context(config, contact, content, args.screenshots)
    html = render_html(context)

    args.out.mkdir(parents=True, exist_ok=True)
    slug = tenant_slug(config["tenant_name"])
    lang = config["language"]
    date = context["generated_date"]
    sha = context["claude_md_sha"]
    base_name = f"Valqeron-Handout_{slug}_{lang}_{date}_{sha}"

    html_path = args.out / f"{base_name}.html"
    pdf_path = args.out / f"{base_name}.pdf"
    html_path.write_text(html, encoding="utf-8")

    html_to_pdf(html_path, pdf_path)
    html_path.unlink()  # intermediate file, not part of the deliverable

    concept_note = " (CONCEPT — contact.json missing or incomplete)" if context["concept_only"] else ""
    print(f"Wrote {pdf_path}{concept_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
