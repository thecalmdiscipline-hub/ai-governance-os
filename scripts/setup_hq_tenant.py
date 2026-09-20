"""
Set up the Valqeron HQ ("tenant 0") organization: all BASE_MODULES active,
and optionally deactivate named users (never deletes anything).

Usage (production, as the app user, with the real .env):
    python scripts/setup_hq_tenant.py --organization-id 1 --deactivate-user admin --dry-run
    python scripts/setup_hq_tenant.py --organization-id 1 --deactivate-user admin

Idempotent: a second run changes nothing. Only touches the given
organization. Every change writes an audit line (performed_by="system").
Contains no secrets. Does not set is_super_admin and does not rename the
organization.
"""
import argparse
import os
import sys
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.core.audit import create_audit_log
from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.tenant_module import TenantModule
from app.models.user import User
from app.services.module_access import BASE_MODULES


def apply(db, organization_id: int, deactivate_users: List[str], dry_run: bool) -> List[str]:
    """Returns human-readable lines describing every change (made, or that would be made)."""
    changes: List[str] = []
    prefix = "WOULD " if dry_run else ""

    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if org is None:
        raise SystemExit(f"Organization {organization_id} does not exist")

    # --- modules ---
    for m in BASE_MODULES:
        key = m["key"]
        row = (
            db.query(TenantModule)
            .filter(TenantModule.organization_id == organization_id, TenantModule.module_key == key)
            .first()
        )
        if row is not None and row.is_active:
            continue
        action = "reactivate" if row is not None else "activate"
        changes.append(f"{prefix}{action} module {key} for org {organization_id}")
        if dry_run:
            continue
        if row is None:
            row = TenantModule(organization_id=organization_id, module_key=key, is_active=True)
            db.add(row)
        else:
            row.is_active = True
        db.commit()
        db.refresh(row)
        create_audit_log(
            db,
            organization_id=organization_id,
            entity_type="tenant_module",
            entity_id=row.id,
            action="module_activated",
            details=f"HQ setup: module {key} activated",
            performed_by="system",
        )

    # --- users to deactivate (never delete) ---
    for username in deactivate_users:
        user = (
            db.query(User)
            .filter(User.username == username, User.organization_id == organization_id)
            .first()
        )
        if user is None:
            raise SystemExit(f"User {username!r} not found in organization {organization_id}")
        if not user.is_active:
            continue
        other_active = (
            db.query(User)
            .filter(User.organization_id == organization_id, User.is_active.is_(True), User.id != user.id)
            .count()
        )
        if other_active == 0:
            raise SystemExit(
                f"Refusing to deactivate {username!r}: it is the last active user of organization {organization_id}"
            )
        changes.append(f"{prefix}deactivate user {username} in org {organization_id}")
        if dry_run:
            continue
        user.is_active = False
        db.commit()
        create_audit_log(
            db,
            organization_id=organization_id,
            entity_type="user",
            entity_id=user.id,
            action="user_deactivated",
            details=f"HQ setup: user {username} deactivated (not deleted)",
            performed_by="system",
        )

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--organization-id", type=int, required=True)
    parser.add_argument("--deactivate-user", action="append", default=[], metavar="USERNAME")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        changes = apply(db, args.organization_id, args.deactivate_user, args.dry_run)
    finally:
        db.close()

    if not changes:
        print("Nothing to change (already in the desired state).")
    for line in changes:
        print(line)
    print(f"{'DRY RUN — nothing written. ' if args.dry_run else ''}{len(changes)} change(s).")


if __name__ == "__main__":
    main()
