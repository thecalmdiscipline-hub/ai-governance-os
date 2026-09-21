"""
Send the e-mail notification again for support requests that did not get one.

Usage (production, as root in /opt/valqeron, with the real .env):
    venv/bin/python scripts/resend_support_notifications.py --dry-run
    venv/bin/python scripts/resend_support_notifications.py

Picks the rows with notify_status "failed" or "skipped_no_config" (for example requests that came in before the
Resend key was configured), oldest first, and sends the same notification as the API does. Rows that were
already "sent" are never touched. Without RESEND_API_KEY, SUPPORT_FROM_EMAIL and SUPPORT_NOTIFY_EMAIL nothing
can be sent: the script says so and exits (a dry run still lists what it would send). Prints references and
counts only, never message text, addresses or keys.
"""
import argparse
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.db.session import SessionLocal
from app.models.support_request import SupportRequest
from app.services import support_mail

RETRY_STATUSES = ("failed", "skipped_no_config")


def resend_pending(db, dry_run: bool) -> Dict[str, object]:
    rows = (
        db.query(SupportRequest)
        .filter(SupportRequest.notify_status.in_(RETRY_STATUSES))
        .order_by(SupportRequest.id)
        .all()
    )
    result: Dict[str, object] = {"candidates": [r.reference for r in rows], "configured": support_mail.is_configured(), "sent": 0, "failed": 0}
    if dry_run or not rows:
        return result
    if not support_mail.is_configured():
        raise SystemExit("Not configured: set RESEND_API_KEY, SUPPORT_FROM_EMAIL and SUPPORT_NOTIFY_EMAIL first. Nothing sent.")
    for row in rows:
        status = support_mail.deliver(db, row)
        result["sent" if status == "sent" else "failed"] += 1  # type: ignore[operator]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="list what would be sent, send nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = resend_pending(db, args.dry_run)
    finally:
        db.close()

    print(f"Candidates ({len(result['candidates'])}): {', '.join(result['candidates']) or '-'}")  # type: ignore[arg-type]
    print(f"Configured: {'yes' if result['configured'] else 'NO (RESEND_API_KEY / SUPPORT_FROM_EMAIL / SUPPORT_NOTIFY_EMAIL)'}")
    if args.dry_run:
        print("DRY RUN - nothing sent.")
    else:
        print(f"Sent: {result['sent']}, failed: {result['failed']}")


if __name__ == "__main__":
    main()
