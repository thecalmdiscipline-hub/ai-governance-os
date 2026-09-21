"""
Grant (or revoke) the super-admin flag. The ONLY way to set is_super_admin: there is no API for it.

Usage (production, as root/app user, with the real .env):
    python scripts/grant_super_admin.py --username X --dry-run
    python scripts/grant_super_admin.py --username X
    python scripts/grant_super_admin.py --username X --revoke

Granting is refused unless the user is active, belongs to the HQ organization
(HQ_ORGANIZATION_ID) and has MFA enabled. Revoking has no such conditions. Idempotent.
Every change writes an audit line (performed_by="system") in the user's own audit chain.
Contains no secrets.
"""
import argparse
import os
import sys
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.core.audit import create_audit_log
from app.core.config import get_hq_organization_id
from app.db.session import SessionLocal
from app.models.user import User


def apply(db, username: str, revoke: bool, dry_run: bool) -> List[str]:
    """Returns human-readable lines describing every change (made, or that would be made)."""
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise SystemExit(f"User {username!r} not found")

    prefix = "WOULD " if dry_run else ""

    if revoke:
        if not user.is_super_admin:
            return []
        action, details = "super_admin_revoked", "Super-admin flag revoked by script"
        message = f"{prefix}revoke super-admin from {username}"
    else:
        hq_org_id = get_hq_organization_id()
        if hq_org_id is None:
            raise SystemExit("HQ_ORGANIZATION_ID is not configured; refusing to grant super-admin")
        if not user.is_active:
            raise SystemExit(f"Refusing: {username!r} is not active")
        if user.organization_id != hq_org_id:
            raise SystemExit(f"Refusing: {username!r} is not in the HQ organization")
        if not user.mfa_enabled:
            raise SystemExit(f"Refusing: {username!r} has no MFA enabled (enroll MFA first)")
        if user.is_super_admin:
            return []
        action, details = "super_admin_granted", "Super-admin flag granted by script"
        message = f"{prefix}grant super-admin to {username}"

    if dry_run:
        return [message]

    user.is_super_admin = not revoke
    db.commit()
    create_audit_log(
        db,
        organization_id=user.organization_id,
        entity_type="user",
        entity_id=user.id,
        action=action,
        details=details,
        performed_by="system",
    )
    return [message]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", required=True)
    parser.add_argument("--revoke", action="store_true", help="remove the super-admin flag instead of granting it")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        changes = apply(db, args.username, args.revoke, args.dry_run)
    finally:
        db.close()

    if not changes:
        print("Nothing to change (already in the desired state).")
    for line in changes:
        print(line)
    print(f"{'DRY RUN - nothing written. ' if args.dry_run else ''}{len(changes)} change(s).")


if __name__ == "__main__":
    main()
