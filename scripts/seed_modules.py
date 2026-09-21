"""
Seed tenant module access from the original hardcoded TENANT_MODULES config.

Usage:
    DATABASE_URL=sqlite+pysqlite:///./test.db python scripts/seed_modules.py

Idempotent: skips rows that already exist.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.services.tenant_modules import ensure_modules

SEED_DATA: dict = {
    1: {
        "core",
        "compliance_monitor",
        "document_intelligence",
        "sales_qualification_ai",
        "business_intelligence",
    },
    2: {
        "core",
        "customer_support_ai",
    },
}


def seed() -> None:
    """Insert-only bootstrap of the original demo/HQ module sets (unchanged behaviour).

    Runs on every deploy (scripts/deploy.sh), so it must never alter an existing organization: it only inserts
    rows that are missing and skips organizations that have a tier (those are managed through the module API,
    and re-adding a module removed there would undo that change). Organizations 1 and 2 have no tier
    (grandfathered), so for them this behaves exactly as before.
    """
    db = SessionLocal()
    inserted = 0
    skipped = 0

    try:
        for org_id, module_keys in SEED_DATA.items():
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if org is not None and org.tier is not None:
                skipped += len(module_keys)
                continue
            ins, skp = ensure_modules(db, org_id, module_keys)
            inserted += ins
            skipped += skp

        db.commit()
        print(f"Seed complete — inserted: {inserted}, skipped (already present): {skipped}")
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
