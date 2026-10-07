"""
Batch N3 (2026-10-07): one-off, idempotent correction of the old monitoring_commitment overclaim
on a single organization's AIPolicy row(s). Runs on the server over SSH.

Usage (as root, in /opt/valqeron, with the real .env):
    venv/bin/python scripts/fix_monitoring_commitment.py --org 3 --dry-run
    venv/bin/python scripts/fix_monitoring_commitment.py --org 3

Only touches a row whose monitoring_commitment is EXACTLY the old overclaim text
("... AI systems are monitored continuously; incidents are recorded and followed up."). Any other
value (including the already-corrected text, or anything a client may have edited) is left alone
and reported, never overwritten. Writes an audit line per corrected row with
performed_by="system:fix_monitoring_commitment"; the audit details never contain the policy text
itself, only the policy id. Idempotent: running it twice makes no further change the second time.
"""
import argparse
import os
import sys
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.core.audit import create_audit_log
from app.core.provisioning_defaults import MONITORING_COMMITMENT_TEXT, STANDARD_NOTICE
from app.db.session import SessionLocal
from app.models.ai_policy import AIPolicy

OLD_TEXT = f"{STANDARD_NOTICE} AI systems are monitored continuously; incidents are recorded and followed up."
NEW_TEXT = f"{STANDARD_NOTICE} {MONITORING_COMMITMENT_TEXT}"


def apply(db, organization_id: int, dry_run: bool) -> List[str]:
    """Returns human-readable lines describing every change (made, or that would be made)."""
    rows = db.query(AIPolicy).filter(AIPolicy.organization_id == organization_id).all()
    if not rows:
        return [f"No AIPolicy row found for organization {organization_id}."]

    lines: List[str] = []
    prefix = "WOULD " if dry_run else ""
    for row in rows:
        if row.monitoring_commitment != OLD_TEXT:
            lines.append(f"SKIPPED policy id={row.id}: monitoring_commitment is not the exact old overclaim text.")
            continue

        lines.append(f"{prefix}correct policy id={row.id} for organization {organization_id}")
        if dry_run:
            continue

        row.monitoring_commitment = NEW_TEXT
        db.commit()
        create_audit_log(
            db,
            organization_id=organization_id,
            entity_type="ai_policy",
            entity_id=row.id,
            action="monitoring_commitment_corrected",
            details=f"monitoring_commitment text corrected on policy id {row.id}",
            performed_by="system:fix_monitoring_commitment",
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--org", required=True, type=int, dest="organization_id")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        lines = apply(db, args.organization_id, args.dry_run)
    finally:
        db.close()

    for line in lines:
        print(line)
    changed = sum(1 for line in lines if line.startswith(("correct", "WOULD correct")))
    print(f"{'DRY RUN - nothing written. ' if args.dry_run else ''}{changed} row(s) corrected.")


if __name__ == "__main__":
    main()
