"""
Seed the 'standard-v1' onboarding template (Batch I, Fase 2.2).

Usage:
    DATABASE_URL=sqlite+pysqlite:///./test.db python scripts/seed_onboarding_templates.py --dry-run
    venv/bin/python scripts/seed_onboarding_templates.py

Idempotent, insert-only: does nothing if 'standard-v1' already exists (mirrors
scripts/seed_modules.py). The template's content is the single list in
app/services/onboarding.py's STANDARD_V1_TASKS, not duplicated here.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.db.session import SessionLocal
from app.services.onboarding import seed_standard_v1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="report what would be inserted, write nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = seed_standard_v1(db, dry_run=args.dry_run)
    finally:
        db.close()

    if result["created"]:
        verb = "would insert" if args.dry_run else "inserted"
        print(f"standard-v1: {verb} 1 template + {result['tasks_inserted']} tasks")
    else:
        print(f"standard-v1: already exists (template_id={result['template_id']}, {result['existing_tasks']} tasks) — nothing to do")

    if args.dry_run:
        print("DRY RUN - nothing written.")


if __name__ == "__main__":
    main()
