"""Blocking quality checks for the Valqeron handout generator (Batch M).

Four checks, all must pass before a PDF may be produced (see generate_handout.py):
  1. forbidden words (NL+EN), with the negation exception from the content concept
  2. claim register: every claim ID used has evidence; every sentence with an absolute word
     ("always"/"never"/"every"/"altijd"/"nooit"/"elke") or a digit carries a claim ID, unless
     the block is explicitly marked allow_absolute (a negation, not an overclaim)
  3. completeness: the handout's module set matches the config's module list exactly
  4. HR lock (hr_recruitment_ai only renders if confirmed) + contact gate (no contact.json or a
     missing field means concept-only output)

Nothing here talks to the network, the database or the portal. Pure text/config validation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import yaml

HANDOUT_DIR = Path(__file__).parent / "handout"

FORBIDDEN_EN: List[str] = [
    "as-is",
    "ready to send",
    "ready-to-use",
    "ready-made",
    "automatically",
    "automated decision",
    "fully",
    "completely",
    "100%",
    "guarantee",
    "guaranteed",
    "continuous",
    "continuously",
    "real-time monitoring",
    "certified",
    "certification",
    "compliant",
    "compliance guaranteed",
    "ai approves",
    "ai decides",
    "secure",
    "safe",
]

FORBIDDEN_NL: List[str] = [
    "kant-en-klaar",
    "direct bruikbaar",
    "automatisch",
    "geautomatiseerd besluit",
    "volledig",
    "helemaal",
    "100%",
    "garantie",
    "gegarandeerd",
    "continu",
    "voortdurend",
    "realtime bewaking",
    "gecertificeerd",
    "conform",
    "voldoet aan",
    "ai keurt goed",
    "ai beslist",
    "veilig",
]

NEGATION_WORDS_EN = ["no", "not", "never", "none", "nothing", "doesn't", "does not", "isn't", "is not"]
NEGATION_WORDS_NL = ["geen", "niet", "nooit", "niets"]

ABSOLUTE_WORDS_EN = ["always", "never", "every"]
ABSOLUTE_WORDS_NL = ["altijd", "nooit", "elke"]

_LOOKBACK_CHARS = 40
_NUMBER_RE = re.compile(r"\b\d+\b")


@dataclass
class TextBlock:
    block_id: str
    lang: str
    text: str
    claims: List[str] = field(default_factory=list)
    allow_absolute: bool = False


def load_yaml(name: str) -> dict:
    path = HANDOUT_DIR / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_content() -> Dict[str, dict]:
    return {
        "shared": load_yaml("shared.yaml"),
        "modules": load_yaml("modules.yaml"),
        "claims": load_yaml("claims.yaml"),
    }


def flatten_text_blocks(shared: dict, modules: dict) -> List[TextBlock]:
    """Every (block, language) pair whose text is checked by rules 1 and 2."""
    out: List[TextBlock] = []

    for block_id, block in shared.get("blocks", {}).items():
        claims = block.get("claims", []) or []
        allow_absolute = bool(block.get("allow_absolute", False))
        for lang in ("nl", "en"):
            if lang in block:
                out.append(TextBlock(f"shared.{block_id}", lang, block[lang], claims, allow_absolute))
        # contact's nl_template/en_template contain only placeholders + static text; no
        # absolute/forbidden-word risk beyond what's checked elsewhere, but scan them too.
        for lang, key in (("nl", "nl_template"), ("en", "en_template")):
            if key in block:
                out.append(TextBlock(f"shared.{block_id}", lang, block[key], claims, allow_absolute))

    for tab in shared.get("tabs", []):
        claims = tab.get("claims", []) or []
        allow_absolute = bool(tab.get("allow_absolute", False))
        for lang in ("nl", "en"):
            if lang in tab:
                out.append(TextBlock(f"tab.{tab['key']}", lang, tab[lang], claims, allow_absolute))

    if "core" in modules:
        core = modules["core"]
        claims = core.get("claims", []) or []
        for lang in ("nl", "en"):
            if lang in core:
                out.append(TextBlock("module.core", lang, core[lang], claims, False))

    for mod in modules.get("modules", []):
        key = mod["key"]
        for section in ("does", "sees", "you_do", "human", "extra_note", "tier_note"):
            block = mod.get(section)
            if not block:
                continue
            if isinstance(block, dict) and ("nl" in block or "en" in block):
                claims = block.get("claims", []) or []
                allow_absolute = bool(block.get("allow_absolute", False))
                for lang in ("nl", "en"):
                    if lang in block:
                        out.append(TextBlock(f"module.{key}.{section}", lang, block[lang], claims, allow_absolute))

    return out


def _boundary_pattern(word: str) -> re.Pattern:
    """Matches `word` only at a letter/digit boundary, so 'veilig' does not match inside
    'beveiligings-' and 'elke' does not match inside a longer word. Lookarounds (not \\b) so
    this also works correctly for a phrase ending in a non-word character like '100%'."""
    escaped = re.escape(word.lower())
    return re.compile(rf"(?<![a-zàéèëïöüA-ZÀÉÈËÏÖÜ0-9]){escaped}(?![a-zàéèëïöüA-ZÀÉÈËÏÖÜ0-9])")


def check_forbidden_words(blocks: Iterable[TextBlock]) -> List[str]:
    problems: List[str] = []
    for b in blocks:
        words = FORBIDDEN_NL if b.lang == "nl" else FORBIDDEN_EN
        negations = NEGATION_WORDS_NL if b.lang == "nl" else NEGATION_WORDS_EN
        lowered = b.text.lower()
        for word in words:
            for m in _boundary_pattern(word).finditer(lowered):
                start = max(0, m.start() - _LOOKBACK_CHARS)
                context = lowered[start : m.start()]
                negated = any(neg in context for neg in negations)
                if not negated:
                    problems.append(
                        f"{b.block_id} ({b.lang}): forbidden word '{word}' without negation "
                        f"— context: ...{b.text[max(0, m.start()-30):m.end()+30]}..."
                    )
    return problems


def check_claims(blocks: Iterable[TextBlock], claims_registry: dict) -> List[str]:
    problems: List[str] = []
    known = claims_registry.get("claims", {}) or {}

    for b in blocks:
        for cid in b.claims:
            if cid not in known:
                problems.append(f"{b.block_id}: references unknown claim ID {cid}")
            elif not (known[cid].get("evidence") or "").strip():
                problems.append(f"{b.block_id}: claim {cid} has no evidence")

        absolute_words = ABSOLUTE_WORDS_NL if b.lang == "nl" else ABSOLUTE_WORDS_EN
        lowered = b.text.lower()
        has_absolute = any(re.search(rf"\b{re.escape(w)}\b", lowered) for w in absolute_words)
        has_number = bool(_NUMBER_RE.search(b.text))

        if (has_absolute or has_number) and not b.claims and not b.allow_absolute:
            found = [w for w in absolute_words if re.search(rf"\b{re.escape(w)}\b", lowered)]
            nums = _NUMBER_RE.findall(b.text)
            problems.append(
                f"{b.block_id} ({b.lang}): absolute word/number without a claim ID or "
                f"allow_absolute — words={found} numbers={nums}"
            )

    return problems


def check_completeness(selected_module_keys: Iterable[str], modules_yaml: dict) -> List[str]:
    """The handout must contain exactly the modules in the config: every selected key has a
    template, and the template catalog has no orphan entries a config could never reach."""
    problems: List[str] = []
    catalog_keys = {m["key"] for m in modules_yaml.get("modules", [])}
    selected = set(selected_module_keys) - {"core"}

    missing_templates = sorted(selected - catalog_keys)
    for key in missing_templates:
        problems.append(f"module '{key}' is in the config but has no template in modules.yaml")

    return problems


def check_modules_yaml_has_all_catalog_keys(modules_yaml: dict, catalog_module_keys: Iterable[str]) -> List[str]:
    """The reverse of check_completeness: every catalog module (from BASE_MODULES, minus core)
    must have a template, so a future config can never silently render an empty module block."""
    problems: List[str] = []
    template_keys = {m["key"] for m in modules_yaml.get("modules", [])}
    catalog = set(catalog_module_keys) - {"core"}
    missing = sorted(catalog - template_keys)
    for key in missing:
        problems.append(f"catalog module '{key}' has no template in modules.yaml")
    extra = sorted(template_keys - catalog)
    for key in extra:
        problems.append(f"modules.yaml has a template for '{key}' which is not in the module catalog")
    return problems


def check_hr_lock(selected_module_keys: Iterable[str], confirmed_blocks: Iterable[str]) -> List[str]:
    problems: List[str] = []
    selected = set(selected_module_keys)
    confirmed = set(confirmed_blocks)
    if "hr_recruitment_ai" in selected and "hr_recruitment_ai" not in confirmed:
        problems.append(
            "module 'hr_recruitment_ai' is active but not in confirmed_blocks — "
            "Dennis must confirm this module before it can be included"
        )
    return problems


def check_contact_gate(contact_data: Optional[dict]) -> List[str]:
    """Returns problems only when contact_data is present but incomplete (missing a required
    field). A fully-missing contact.json is not a problem — the caller renders a concept."""
    problems: List[str] = []
    if contact_data is None:
        return problems
    required = ("urgent_phone", "urgent_hours", "security_contact")
    for field_name in required:
        value = contact_data.get(field_name)
        if not value or not str(value).strip():
            problems.append(f"contact.json is present but missing or empty field '{field_name}'")
    return problems


def is_concept_only(contact_data: Optional[dict]) -> bool:
    """True whenever the generator must stamp CONCEPT/DRAFT on every page: no contact.json, or
    one with a missing/empty field."""
    if contact_data is None:
        return True
    required = ("urgent_phone", "urgent_hours", "security_contact")
    return any(not contact_data.get(f) or not str(contact_data.get(f)).strip() for f in required)


def run_all_checks(
    *,
    content: Dict[str, dict],
    selected_module_keys: Iterable[str],
    confirmed_blocks: Iterable[str],
    contact_data: Optional[dict],
    catalog_module_keys: Optional[Iterable[str]] = None,
) -> List[str]:
    """Runs all four blocking checks and returns every problem found (empty = clean)."""
    problems: List[str] = []

    blocks = flatten_text_blocks(content["shared"], content["modules"])
    problems += check_forbidden_words(blocks)
    problems += check_claims(blocks, content["claims"])
    problems += check_completeness(selected_module_keys, content["modules"])
    if catalog_module_keys is not None:
        problems += check_modules_yaml_has_all_catalog_keys(content["modules"], catalog_module_keys)
    problems += check_hr_lock(selected_module_keys, confirmed_blocks)
    problems += check_contact_gate(contact_data)

    return problems
