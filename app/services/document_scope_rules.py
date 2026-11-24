"""Fase B7 (V2): suggested scope codes for an upload, from config/document_scope_rules.yaml.

Suggestions only: nothing is stored and no code is assigned. The upload route is unchanged and still
requires the confirmed codes in the filename and on the first line (V1/V5).

The rules file is loaded once, when this module is imported (at app start, via app/api/documents.py).
An invalid file stops the app with a ScopeRulesError naming the rule and the problem: it never falls
back silently to "no rules".
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # PyYAML: already installed (dependency of presidio-analyzer), no new dependency

from app.services.document_scope import ScopeValidationError, validate_scopes
from app.services.document_scope_codes import EXCLUSIVE_CODES

RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "document_scope_rules.yaml"

# Only the start of a document is scanned for keywords.
MAX_SCAN_CHARS = 20000


class ScopeRulesError(RuntimeError):
    pass


def _str_list(rule_name: str, field: str, value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ScopeRulesError(f"document_scope_rules: rule '{rule_name}': '{field}' must be a list of non-empty strings")
    return [v.strip().lower() for v in value]


def load_rules(path: Path = RULES_PATH) -> List[Dict[str, Any]]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ScopeRulesError(f"document_scope_rules: file not found: {path}")
    except yaml.YAMLError as exc:
        raise ScopeRulesError(f"document_scope_rules: invalid YAML in {path}: {exc}")

    if not isinstance(raw, dict) or not isinstance(raw.get("rules"), list):
        raise ScopeRulesError(f"document_scope_rules: {path} must contain a top-level 'rules' list")

    rules: List[Dict[str, Any]] = []
    seen = set()
    for i, item in enumerate(raw["rules"], start=1):
        if not isinstance(item, dict):
            raise ScopeRulesError(f"document_scope_rules: rule #{i} is not a mapping")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ScopeRulesError(f"document_scope_rules: rule #{i} has no name")
        name = name.strip()
        if name in seen:
            raise ScopeRulesError(f"document_scope_rules: duplicate rule name '{name}'")
        seen.add(name)
        unknown_keys = set(item) - {"name", "document_types", "keywords", "match", "codes"}
        if unknown_keys:
            raise ScopeRulesError(f"document_scope_rules: rule '{name}': unknown field(s) {sorted(unknown_keys)}")

        types = [t.lstrip(".") for t in _str_list(name, "document_types", item.get("document_types"))]
        keywords = _str_list(name, "keywords", item.get("keywords"))
        if not types and not keywords:
            raise ScopeRulesError(f"document_scope_rules: rule '{name}' needs document_types or keywords")
        match = item.get("match", "any")
        if match not in ("any", "all"):
            raise ScopeRulesError(f"document_scope_rules: rule '{name}': match must be 'any' or 'all'")
        if match == "all" and not (types and keywords):
            raise ScopeRulesError(f"document_scope_rules: rule '{name}': match 'all' needs document_types and keywords")

        codes = _str_list(name, "codes", item.get("codes"))
        try:
            validate_scopes(codes)
        except ScopeValidationError as exc:
            raise ScopeRulesError(f"document_scope_rules: rule '{name}': {exc.message} ({exc.error})")

        rules.append({
            "name": name, "document_types": types, "keywords": keywords, "match": match,
            "codes": sorted(set(codes)),
            # whole words only: no letter or digit directly before or after the keyword
            "patterns": [re.compile(rf"(?<![^\W_]){re.escape(k)}(?![^\W_])") for k in keywords],
        })
    return rules


RULES: List[Dict[str, Any]] = load_rules()


def suggest_codes(filename: str, text: Optional[str], rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Suggested codes for a file. A file without readable text gets no suggestion: it cannot carry
    the required 'scope:' first line, so its upload would be refused anyway."""
    rules = RULES if rules is None else rules
    if not text or not text.strip():
        return {"readable": False, "suggested_codes": [], "matched_rules": []}

    ext = Path(filename).suffix.lower().lstrip(".")
    haystack = f"{filename}\n{text[:MAX_SCAN_CHARS]}".lower()
    matched, codes = [], set()
    for rule in rules:
        type_hit = ext in rule["document_types"]
        word_hit = any(p.search(haystack) for p in _patterns(rule))
        hit = (type_hit and word_hit) if rule.get("match", "any") == "all" else (type_hit or word_hit)
        if hit:
            matched.append(rule["name"])
            codes.update(rule["codes"])
    # B3a: an exclusive code ('hr') is never suggested together with another code. When it matches,
    # it wins: suggesting only 'hr' keeps a possibly personal document away from other workflows.
    exclusive = codes & EXCLUSIVE_CODES
    if exclusive:
        codes = {sorted(exclusive)[0]}
    return {"readable": True, "suggested_codes": sorted(codes), "matched_rules": matched}


def _patterns(rule: Dict[str, Any]) -> List["re.Pattern[str]"]:
    if "patterns" not in rule:  # rules built by hand (tests) instead of by load_rules
        rule["patterns"] = [re.compile(rf"(?<![^\W_]){re.escape(k.lower())}(?![^\W_])") for k in rule["keywords"]]
    return rule["patterns"]
