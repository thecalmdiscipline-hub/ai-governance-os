"""
Emergency reset of a user's MFA (lock-out procedure). Runs on the server over SSH.

Usage (as root, in /opt/valqeron, with the real .env):
    venv/bin/python scripts/mfa_reset.py --username X --dry-run
    venv/bin/python scripts/mfa_reset.py --username X

Wipes every MFA field of the user (secret, backup codes, last step, failed attempts, lock) and sets
mfa_enabled=false, so the user can log in with just the password again and enroll MFA anew.
A super-admin keeps the is_super_admin flag, but has no /ops access again until they have enrolled
MFA and logged in with it (the token claim is only accepted while MFA is enabled).
Writes an audit line with performed_by="system:mfa_reset". Idempotent. Contains no secrets and
never prints any.
"""
import argparse
import os
import sys
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.api.mfa import clear_mfa
from app.core.audit import create_audit_log
from app.db.session import SessionLocal
from app.models.user import User


def _has_mfa_state(user: User) -> bool:
    return bool(
        user.mfa_enabled
        or user.mfa_secret_enc
        or user.mfa_backup_codes
        or user.mfa_last_step is not None
        or user.mfa_failed_attempts
        or user.mfa_locked_until
    )


def apply(db, username: str, dry_run: bool) -> List[str]:
    """Returns human-readable lines describing every change (made, or that would be made)."""
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise SystemExit(f"User {username!r} not found")
    if not _has_mfa_state(user):
        return []

    prefix = "WOULD " if dry_run else ""
    note = " (super-admin flag stays; /ops needs a new MFA enrollment)" if user.is_super_admin else ""
    message = f"{prefix}reset MFA for {username}{note}"
    if dry_run:
        return [message]

    clear_mfa(user)
    db.commit()
    if user.organization_id is not None:
        create_audit_log(
            db,
            organization_id=user.organization_id,
            entity_type="user_mfa",
            entity_id=user.id,
            action="mfa_reset",
            details="MFA reset by the emergency script; all MFA data removed",
            performed_by="system:mfa_reset",
        )
    return [message]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", required=True)
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        changes = apply(db, args.username, args.dry_run)
    finally:
        db.close()

    if not changes:
        print("Nothing to change (this user has no MFA data).")
    for line in changes:
        print(line)
    print(f"{'DRY RUN - nothing written. ' if args.dry_run else ''}{len(changes)} change(s).")


if __name__ == "__main__":
    main()
