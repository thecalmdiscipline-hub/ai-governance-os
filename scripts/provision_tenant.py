"""
Provision a new customer from a JSON config, on the server (the CLI twin of POST /ops/tenants/provision).

Usage (production, as root in /opt/valqeron, with the real .env):
    venv/bin/python scripts/provision_tenant.py --config klant.json --dry-run
    venv/bin/python scripts/provision_tenant.py --config klant.json
    venv/bin/python scripts/provision_tenant.py --config klant.json --password-file /root/klant-wachtwoord.txt

Config keys: idempotency_key, organization_name, country, sector, tier (starter|business|enterprise),
modules (list of module keys, incl. "core"), admin_username, admin_email (validated, not stored),
include_demo_document (default true), include_demo_run (default false).

Runs the same service as the API (one transaction, idempotent, tier rules), with audit lines written
as performed_by="system:provision_cli". The one-time admin password is printed to stdout, or, with
--password-file, written to a new file with mode 600 (an existing file is never overwritten) and not printed.
A repeated run with the same key and config creates nothing and shows no password.
Contains no secrets.
"""
import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.db.session import SessionLocal
from app.services.provisioning import ProvisionParams, ProvisioningError, plan, provision_tenant

CLI_ACTOR = "system:provision_cli"
_ALLOWED = {
    "idempotency_key", "organization_name", "country", "sector", "tier", "modules",
    "admin_username", "admin_email", "include_demo_document", "include_demo_run",
}


def _params(config: Dict[str, Any]) -> ProvisionParams:
    unknown = sorted(set(config) - _ALLOWED)
    if unknown:
        raise SystemExit(f"Unknown config keys: {', '.join(unknown)}")
    missing = [k for k in ("idempotency_key", "organization_name", "tier", "modules", "admin_username") if k not in config]
    if missing:
        raise SystemExit(f"Missing config keys: {', '.join(missing)}")
    return ProvisionParams(**config)


def _write_password_file(path: str, password: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)  # O_EXCL: never overwrite
    with os.fdopen(fd, "w") as f:
        f.write(password + "\n")


def apply(db, config: Dict[str, Any], dry_run: bool, password_file: Optional[str] = None) -> Dict[str, Any]:
    """Returns the result dict. The password is NOT part of it when it was written to a file."""
    params = _params(config)
    try:
        if dry_run:
            return plan(db, params)
        if password_file and os.path.exists(password_file):
            raise SystemExit(f"Refusing to overwrite {password_file}")
        result = provision_tenant(db, params, actor=None, performed_by=CLI_ACTOR)
    except ProvisioningError as exc:
        raise SystemExit(f"Refused ({exc.status} {exc.code}): " + "; ".join(exc.problems))
    if password_file and result.get("admin_password"):
        _write_password_file(password_file, result.pop("admin_password"))
        result["admin_password_file"] = password_file
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, help="path to the JSON config")
    parser.add_argument("--dry-run", action="store_true", help="validate and show what would be created, write nothing")
    parser.add_argument("--password-file", help="write the one-time password to this NEW file (mode 600) instead of stdout")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    db = SessionLocal()
    try:
        result = apply(db, config, args.dry_run, args.password_file)
    finally:
        db.close()

    password = result.pop("admin_password", None)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.dry_run:
        print("DRY RUN - nothing written.")
    if password:
        print(f"admin_password: {password}")
        print("Shown once. The user must change it at first login.")


if __name__ == "__main__":
    main()
