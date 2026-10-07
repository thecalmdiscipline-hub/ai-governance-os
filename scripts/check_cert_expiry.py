"""
Batch R3 (2026-10-07): read-only TLS certificate expiry check for the three production domains.
Opens a real TLS handshake (stdlib ssl/socket, no new dependency), reads the certificate's
notAfter date, and reports the number of days remaining. No writes, no secrets.

Usage:
    python3 scripts/check_cert_expiry.py                              # the three default domains
    python3 scripts/check_cert_expiry.py example.com other.example    # or any domain list
    python3 scripts/check_cert_expiry.py --warning-days 30

Exit code 0: every domain has at least --warning-days (default 21) days left.
Exit code 1: at least one domain is below that threshold, or the handshake itself failed.
"""
import argparse
import datetime
import socket
import ssl
import sys
from typing import Dict, List, Optional

DEFAULT_DOMAINS = ["api.valqeron.com", "app.valqeron.com", "compliance.valqeron.com"]
WARNING_DAYS = 21


def get_cert_not_after(hostname: str, port: int = 443, timeout: float = 10.0) -> datetime.datetime:
    """Opens a real TLS connection and returns the certificate's notAfter as a UTC datetime.
    Raises (socket/ssl errors) on any connection or handshake failure — the caller decides how
    to report that; this function makes no judgement about expiry itself."""
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=timeout) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
    # e.g. 'Nov 20 00:00:00 2026 GMT' — the format OpenSSL/Python's ssl module always uses here.
    return datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=datetime.timezone.utc
    )


def check_domain(hostname: str, warning_days: int = WARNING_DAYS) -> Dict[str, object]:
    try:
        not_after = get_cert_not_after(hostname)
    except Exception as exc:
        return {"domain": hostname, "ok": False, "error": str(exc), "days_remaining": None}

    now = datetime.datetime.now(datetime.timezone.utc)
    days_remaining = (not_after - now).days
    return {"domain": hostname, "ok": days_remaining >= warning_days, "days_remaining": days_remaining, "error": None}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("domains", nargs="*", default=DEFAULT_DOMAINS)
    parser.add_argument("--warning-days", type=int, default=WARNING_DAYS)
    args = parser.parse_args(argv)

    exit_code = 0
    for domain in args.domains:
        result = check_domain(domain, args.warning_days)
        if result["error"]:
            print(f"{domain}: ERROR - {result['error']}")
            exit_code = 1
        else:
            print(f"{domain}: {result['days_remaining']} days remaining")
            if not result["ok"]:
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
