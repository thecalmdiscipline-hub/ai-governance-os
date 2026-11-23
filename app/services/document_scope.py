"""Parsing and validation of document scope codes (Fase B, V1/V4/V5/V18).

The allowed codes come from app/services/document_scope_codes.py only.
"""
import re
from typing import Iterable, Optional, Set

from app.services.document_scope_codes import ALLOWED_CODES, EXCLUSIVE_CODES

_CODE_FORMAT = re.compile(r"^[a-z0-9-]{2,24}$")
_FILENAME_SCOPE = re.compile(r"\[scope=([^\]]*)\]", re.IGNORECASE)
_CONTENT_PREFIX = "scope:"


class ScopeValidationError(ValueError):
    """Raised when a set of scope codes is not acceptable. `error` is a stable machine code."""

    def __init__(self, error: str, message: str):
        super().__init__(message)
        self.error = error
        self.message = message


def _split_codes(raw: str) -> Set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def parse_scope_from_filename(name: Optional[str]) -> Optional[Set[str]]:
    """Codes from a `[scope=a,b]` marker in the filename, or None if there is no marker."""
    if not name:
        return None
    matches = _FILENAME_SCOPE.findall(name)
    if len(matches) != 1:
        # none, or ambiguous (two markers): treat as missing so the upload is refused
        return None
    return _split_codes(matches[0])


def parse_scope_from_content(text: Optional[str]) -> Optional[Set[str]]:
    """Codes from the first non-empty line `scope: a,b`, or None if that line is not a scope line."""
    if not text:
        return None
    for line in text.splitlines():
        stripped = line.strip().lstrip("﻿")
        if not stripped:
            continue
        if stripped.lower().startswith(_CONTENT_PREFIX):
            return _split_codes(stripped[len(_CONTENT_PREFIX):])
        return None
    return None


def validate_scopes(codes: Optional[Iterable[str]]) -> None:
    """Raise ScopeValidationError unless `codes` is a valid, non-empty set of known codes."""
    code_set = set(codes or [])
    if not code_set:
        raise ScopeValidationError("scope_missing", "At least one scope code is required.")
    bad_format = sorted(c for c in code_set if not _CODE_FORMAT.match(c))
    if bad_format:
        raise ScopeValidationError("scope_invalid_format", "Scope codes must be 2-24 characters: a-z, 0-9 or '-'.")
    unknown = sorted(code_set - ALLOWED_CODES)
    if unknown:
        raise ScopeValidationError("scope_unknown", f"Unknown scope code(s): {', '.join(unknown)}.")
    exclusive = code_set & EXCLUSIVE_CODES
    if exclusive and len(code_set) > 1:
        raise ScopeValidationError(
            "scope_exclusive_combined",
            f"Scope code(s) {', '.join(sorted(exclusive))} cannot be combined with another code.",
        )


def scopes_for_upload(filename: Optional[str], text: Optional[str]) -> Set[str]:
    """V1 + V5: codes must be in the filename and on the first line of the content, and be equal."""
    from_name = parse_scope_from_filename(filename)
    from_content = parse_scope_from_content(text)
    if from_name is None and from_content is None:
        raise ScopeValidationError("scope_missing", "No scope code in the filename or on the first line of the content.")
    if from_name is None:
        raise ScopeValidationError("scope_missing_in_filename", "The filename has no [scope=...] marker.")
    if from_content is None:
        raise ScopeValidationError("scope_missing_in_content", "The first line of the content is not 'scope: ...'.")
    if from_name != from_content:
        raise ScopeValidationError("scope_mismatch", "The scope codes in the filename and in the content differ.")
    validate_scopes(from_name)
    return from_name


def effective_scope(doc) -> Set[str]:
    """The codes stored in the database for a document (the database is authoritative)."""
    return {row.code for row in (getattr(doc, "scope_codes", None) or [])}
