"""
Error reporting (Sentry) — errors only, and no customer content.

Valqeron is a processor: request bodies, prompts, documents and local variables
carry customer text and must never reach a third party (Sentry is a
sub-processor). Everything here is therefore opt-in and deliberately narrow:

  - Inactive unless SENTRY_DSN is set (tests, CI and local dev send nothing).
  - Errors only: no tracing, no profiling, no breadcrumbs, no default PII,
    no request bodies, no frame variables.
  - Only an explicit, minimal set of integrations. The SDK's auto-enabling ones
    (OpenAI, SQLAlchemy, httpx, Redis, ...) are switched off because they can
    attach prompts, SQL parameters or response bodies. The logging integration
    stays enabled but records nothing (no breadcrumbs, no events).
  - before_send strips whatever is left down to exception type, file and
    function name (plus a masked, truncated exception message).

The DSN comes from the environment only and is never logged.
"""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

_MAX_TEXT = 200

# Where scripts/deploy.sh writes the short git sha (not in git).
_BUILD_SHA_FILE = Path(__file__).resolve().parents[2] / "BUILD_SHA"
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Six or more digits, optionally separated by spaces, dots or dashes
# (phone numbers, IBAN tails, BSN, card numbers).
_LONG_DIGITS_RE = re.compile(r"\d(?:[ .\-]?\d){5,}")

# Runtime contexts that describe the process, never the customer.
_KEEP_CONTEXTS = ("runtime", "os")


@lru_cache(maxsize=1)
def get_build_sha() -> str:
    """Short git sha of the deployed build, read once; "unknown" when absent/invalid."""
    try:
        value = _BUILD_SHA_FILE.read_text().strip()
    except OSError:
        return "unknown"
    return value if _SHA_RE.match(value) else "unknown"


def scrub_text(value: Any) -> Any:
    """Mask e-mail addresses and long digit runs, then cut to 200 characters."""
    if not isinstance(value, str):
        return value
    value = _EMAIL_RE.sub("[email]", value)
    value = _LONG_DIGITS_RE.sub("[digits]", value)
    return value[:_MAX_TEXT]


def _scrub_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only the method and the URL without query string."""
    cleaned: Dict[str, Any] = {}
    if request.get("method"):
        cleaned["method"] = request["method"]
    url = request.get("url")
    if isinstance(url, str):
        parts = urlsplit(url)
        cleaned["url"] = scrub_text(f"{parts.scheme}://{parts.netloc}{parts.path}" if parts.netloc else parts.path)
    return cleaned


def before_send(event: Dict[str, Any], hint: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Reduce an event to technical facts. Never raises: a broken scrubber must not break the app."""
    try:
        for key in ("user", "extra", "breadcrumbs", "modules", "threads"):
            event.pop(key, None)

        if isinstance(event.get("request"), dict):
            event["request"] = _scrub_request(event["request"])

        if isinstance(event.get("contexts"), dict):
            event["contexts"] = {k: v for k, v in event["contexts"].items() if k in _KEEP_CONTEXTS}

        for key in ("message", "transaction"):
            if key in event:
                event[key] = scrub_text(event[key])
        if isinstance(event.get("logentry"), dict):
            event["logentry"] = {"message": scrub_text(event["logentry"].get("message", ""))}

        for exc in (event.get("exception") or {}).get("values") or []:
            if "value" in exc:
                exc["value"] = scrub_text(exc["value"])
            for frame in (exc.get("stacktrace") or {}).get("frames") or []:
                frame.pop("vars", None)
    except Exception:  # noqa: BLE001
        logger.error("observability: before_send failed; dropping the event")
        return None
    return event


def init_sentry(dsn: Optional[str] = None, transport: Any = None) -> bool:
    """Initialise Sentry when a DSN is configured. Returns whether it is active.

    `dsn` and `transport` exist for tests; production uses the SENTRY_DSN environment variable.
    """
    dsn = (dsn if dsn is not None else os.getenv("SENTRY_DSN", "")).strip()
    if not dsn:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.atexit import AtexitIntegration
    from sentry_sdk.integrations.dedupe import DedupeIntegration
    from sentry_sdk.integrations.excepthook import ExcepthookIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.threading import ThreadingIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        release=get_build_sha(),
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sample_rate=0,
        max_breadcrumbs=0,
        max_value_length=_MAX_TEXT,
        # Explicit allow-list instead of the SDK defaults + auto-enabling integrations.
        default_integrations=False,
        auto_enabling_integrations=False,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
            LoggingIntegration(level=None, event_level=None),
            DedupeIntegration(),
            ExcepthookIntegration(),
            ThreadingIntegration(),
            AtexitIntegration(),
        ],
        before_send=before_send,
        before_breadcrumb=lambda crumb, hint: None,
        transport=transport,
    )
    logger.info("observability: Sentry enabled (release=%s)", get_build_sha())
    return True
