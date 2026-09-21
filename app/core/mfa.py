"""
TOTP second factor (RFC 6238) helpers — no database, no HTTP.

Rules that matter here:
  - The TOTP secret is stored Fernet-encrypted with MFA_ENCRYPTION_KEY (a key of its own,
    not SECRET_KEY). Without the key, enrollment refuses (MFAConfigError -> 503); the rest of
    the app keeps working.
  - Backup codes are random, single-use, and stored only as password hashes (same hasher as
    passwords).
  - A secret, a code or a backup code must never end up in a log line, an audit line, an
    exception message or a Sentry event. Nothing in this module logs or formats them.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import time
from typing import List, Optional

import pyotp
from cryptography.fernet import Fernet, InvalidToken

from app.core.security import hash_password, verify_password

ISSUER = "Valqeron"
STEP_SECONDS = 30
TOLERANCE_STEPS = 1  # accept the previous and next 30 s step (clock drift)
BACKUP_CODE_COUNT = 10
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15

_TOTP_RE = re.compile(r"^\d{6}$")
# No 0/O/1/I/L: backup codes get typed from paper.
_BACKUP_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class MFAConfigError(RuntimeError):
    """MFA_ENCRYPTION_KEY is missing or invalid: enrollment and verification cannot work."""


def _fernet() -> Fernet:
    key = os.getenv("MFA_ENCRYPTION_KEY", "").strip()
    if not key:
        raise MFAConfigError("MFA_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode())
    except Exception as exc:  # noqa: BLE001 - never include the key in the message
        raise MFAConfigError("MFA_ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise MFAConfigError("stored MFA secret cannot be decrypted with the configured key") from exc


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)


def current_step(now: Optional[float] = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def is_totp_format(code: str) -> bool:
    return bool(_TOTP_RE.match(code))


def normalize_code(code: str) -> str:
    return (code or "").strip().replace(" ", "").replace("-", "").upper()


def verify_totp(secret: str, code: str, last_step: Optional[int], now: Optional[float] = None) -> Optional[int]:
    """Return the accepted 30 s step, or None.

    Accepts the current step +/- TOLERANCE_STEPS, but only a step strictly newer than
    `last_step`: the same code (same step) can never be used twice. All candidate steps are
    compared in constant time.
    """
    if not is_totp_format(code):
        return None
    totp = pyotp.TOTP(secret, interval=STEP_SECONDS)
    base = current_step(now)
    accepted: Optional[int] = None
    for step in range(base - TOLERANCE_STEPS, base + TOLERANCE_STEPS + 1):
        expected = totp.at(step * STEP_SECONDS)
        if hmac.compare_digest(expected, code) and (last_step is None or step > last_step):
            accepted = step
    return accepted


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> List[str]:
    """10 random codes like ABCDE-FGHJK (10 chars, ~50 bits each)."""
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_BACKUP_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def hash_backup_codes(codes: List[str]) -> str:
    return json.dumps([hash_password(normalize_code(c)) for c in codes])


def consume_backup_code(stored: Optional[str], code: str) -> Optional[str]:
    """If `code` matches one of the stored hashes, return the stored list without it (JSON), else None.

    Every stored hash is checked (no early exit) so the time taken does not reveal the position.
    """
    if not stored:
        return None
    candidate = normalize_code(code)
    if len(candidate) != 10:
        return None
    hashes = json.loads(stored)
    match_index = None
    for index, hashed in enumerate(hashes):
        if verify_password(candidate, hashed) and match_index is None:
            match_index = index
    if match_index is None:
        return None
    del hashes[match_index]
    return json.dumps(hashes)
