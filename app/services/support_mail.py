"""
E-mail notification for support requests, via the Resend HTTP API (httpx; no SDK).

Rules (Batch G):
  - Works without configuration: without RESEND_API_KEY, SUPPORT_FROM_EMAIL and SUPPORT_NOTIFY_EMAIL nothing is
    sent and the request gets notify_status="skipped_no_config". A missing or failing mail NEVER fails the request.
  - Runs after the request was committed, in a background task with its own database session, with a 10 s timeout.
  - The mail contains: organization name, username, category, subject, reference and the message text (the
    customer wrote it for Valqeron). Nothing else. No Reply-To (there is no customer e-mail address).
  - All customer input is HTML-escaped in the HTML part; the subject line is stripped of control characters.
  - Logs and the stored notify_error are generic: never the API key, the recipient, the subject or the message.
"""
import html
import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.models.support_request import SupportRequest
from app.models.user import User

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10.0
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")


def _config() -> Optional[Dict[str, str]]:
    key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("SUPPORT_FROM_EMAIL", "").strip()
    recipient = os.getenv("SUPPORT_NOTIFY_EMAIL", "").strip()
    if not (key and sender and recipient):
        return None
    return {"key": key, "from": sender, "to": recipient}


def is_configured() -> bool:
    return _config() is not None


def build_message(row: SupportRequest, organization_name: str, username: str) -> Dict[str, str]:
    subject_line = _CONTROL_RE.sub(" ", f"[Valqeron support] {row.reference} {organization_name}").strip()[:200]
    fields = [
        ("Reference", row.reference),
        ("Organization", organization_name),
        ("User", username),
        ("Category", row.category),
        ("Subject", row.subject),
    ]
    text = "\n".join(f"{label}: {value}" for label, value in fields) + "\n\nMessage:\n" + row.message + "\n"
    rows_html = "".join(f"<tr><td><b>{html.escape(label)}</b></td><td>{html.escape(value)}</td></tr>" for label, value in fields)
    message_html = html.escape(row.message).replace("\n", "<br>")
    body_html = f"<table>{rows_html}</table><p><b>Message</b></p><p>{message_html}</p>"
    return {"subject": subject_line, "text": text, "html": body_html}


def send(message: Dict[str, str]) -> Tuple[str, Optional[str]]:
    """Send via Resend. Returns (notify_status, generic error code or None). Never raises."""
    config = _config()
    if config is None:
        return "skipped_no_config", None
    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {config['key']}", "Content-Type": "application/json"},
            json={"from": config["from"], "to": [config["to"]], **message},
            timeout=TIMEOUT_SECONDS,
        )
        if 200 <= response.status_code < 300:
            return "sent", None
        return "failed", f"http_{response.status_code}"
    except httpx.TimeoutException:
        return "failed", "timeout"
    except Exception as exc:  # noqa: BLE001 - only the type name is kept: exception texts could echo request data
        return "failed", f"error_{type(exc).__name__}"


def deliver(db: Session, row: SupportRequest) -> str:
    """Send the notification for one row and record the outcome. Commits. Never raises."""
    try:
        org = db.query(Organization).filter(Organization.id == row.organization_id).first()
        user = db.query(User).filter(User.id == row.user_id).first()
        status, error = send(build_message(row, org.name if org else f"organization {row.organization_id}", user.username if user else "unknown"))
    except Exception as exc:  # noqa: BLE001
        status, error = "failed", f"error_{type(exc).__name__}"
    row.notify_status = status
    row.notify_error = error
    row.notified_at = datetime.utcnow() if status == "sent" else None
    db.commit()
    if status == "failed":
        logger.warning("support notification for %s failed (%s)", row.reference, error)
    else:
        logger.info("support notification for %s: %s", row.reference, status)
    return status


def notify_support_request(request_id: int) -> None:
    """Background task: own session, after the request was committed. Never raises."""
    db = SessionLocal()
    try:
        row = db.query(SupportRequest).filter(SupportRequest.id == request_id).first()
        if row is not None:
            deliver(db, row)
    except Exception:  # noqa: BLE001
        logger.warning("support notification task failed for request id %s", request_id)
    finally:
        db.close()
