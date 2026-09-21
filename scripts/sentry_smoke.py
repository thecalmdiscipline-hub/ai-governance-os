"""
Send exactly ONE test event to Sentry, to verify the privacy setup end to end.

Run on the server with the production environment (as the app user):
    cd /opt/valqeron && venv/bin/python scripts/sentry_smoke.py --send

The event carries a fake e-mail address in the exception message AND in a
local variable, plus the tag smoke_test=true. In Sentry the fake address must
appear nowhere (masked as [email] in the message, no local variables at all).
Refuses to run without SENTRY_DSN or without --send (quota: one event only).
The DSN is never printed.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

FAKE_EMAIL = "test.person@example.com"


def trigger_error() -> None:
    fake_customer_text = f"Please contact {FAKE_EMAIL} about invoice 1234567890"  # noqa: F841 — local variable on purpose
    raise ValueError(f"sentry smoke test: contact {FAKE_EMAIL}")


def main() -> int:
    if "--send" not in sys.argv:
        print("Dry run: pass --send to send exactly one test event.")
        return 2
    if not os.getenv("SENTRY_DSN", "").strip():
        print("SENTRY_DSN is not set; nothing sent.")
        return 1

    import sentry_sdk

    from app.core.observability import get_build_sha, init_sentry

    if not init_sentry():
        print("Sentry did not initialise; nothing sent.")
        return 1
    sentry_sdk.set_tag("smoke_test", "true")
    try:
        trigger_error()
    except ValueError:
        event_id = sentry_sdk.capture_exception()
    sentry_sdk.flush(timeout=10)
    print(f"Sent 1 event: id={event_id} release={get_build_sha()} tag smoke_test=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
