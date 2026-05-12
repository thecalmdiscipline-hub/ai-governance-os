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
from app.models.tenant_module import TenantModule

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
    db = SessionLocal()
    inserted = 0
    skipped = 0

    try:
        for org_id, module_keys in SEED_DATA.items():
            for key in sorted(module_keys):
                exists = (
                    db.query(TenantModule)
                    .filter(
                        TenantModule.organization_id == org_id,
                        TenantModule.module_key == key,
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                else:
                    db.add(
                        TenantModule(
                            organization_id=org_id,
                            module_key=key,
                            is_active=True,
                        )
                    )
                    inserted += 1

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
