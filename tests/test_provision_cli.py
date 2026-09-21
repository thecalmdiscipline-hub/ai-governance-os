"""Batch F, deel 3: scripts/provision_tenant.py (the CLI twin of the provisioning endpoint)."""
import importlib
import json
import os
import stat
import uuid

import pytest
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.core import security
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.user import User
from app.services import tenant_modules as tm

cli = importlib.import_module("scripts.provision_tenant")
WORKFLOWS = sorted(tm.workflow_keys())


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    db = SessionLocal()
    hq = Organization(name=f"cli-hq-{uuid.uuid4().hex[:8]}")
    db.add(hq)
    db.commit()
    monkeypatch.setenv("HQ_ORGANIZATION_ID", str(hq.id))
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(security, "pwd_context", CryptContext(schemes=["bcrypt"], bcrypt__rounds=4))
    db.close()


def _config(**overrides):
    others = [k for k in WORKFLOWS if k != tm.COMPLIANCE_KEY]
    cfg = {
        "idempotency_key": f"cli-{uuid.uuid4().hex[:10]}",
        "organization_name": f"CLI Customer {uuid.uuid4().hex[:8]}",
        "country": "NL",
        "sector": "Testing",
        "tier": "starter",
        "modules": ["core"] + others[:2],
        "admin_username": f"cli_admin_{uuid.uuid4().hex[:8]}",
        "admin_email": "admin@example.com",
    }
    cfg.update(overrides)
    return cfg


def _apply(cfg, dry_run=False, password_file=None):
    db = SessionLocal()
    try:
        return cli.apply(db, cfg, dry_run, password_file)
    finally:
        db.close()


def _org_count(name):
    db = SessionLocal()
    try:
        return db.query(Organization).filter(Organization.name == name).count()
    finally:
        db.close()


def test_dry_run_validates_and_writes_nothing():
    cfg = _config()
    plan = _apply(cfg, dry_run=True)
    assert plan["would_create"] is True and plan["counts"]["ai_systems"] == 2 and plan["counts"]["documents"] == 1
    assert _org_count(cfg["organization_name"]) == 0
    with pytest.raises(SystemExit, match="at least 2 workflows"):
        _apply(_config(modules=["core"]), dry_run=True)


def test_creates_the_tenant_and_audits_as_system_provision_cli():
    cfg = _config()
    result = _apply(cfg)
    assert result["created"] is True and len(result["admin_password"]) >= 20
    db = SessionLocal()
    lines = db.query(AuditLog).filter(AuditLog.action == "tenant_provisioned", AuditLog.entity_id.in_([result["organization_id"], int(os.environ["HQ_ORGANIZATION_ID"])])).all()
    admin = db.query(User).filter(User.username == cfg["admin_username"]).first()
    db.close()
    assert lines and all(r.performed_by == "system:provision_cli" for r in lines)
    assert admin.must_change_password is True
    assert result["admin_password"] not in json.dumps([r.details for r in lines])


def test_password_file_is_mode_600_never_overwritten_and_password_not_in_the_result(tmp_path):
    cfg = _config()
    target = tmp_path / "pw.txt"
    result = _apply(cfg, password_file=str(target))
    assert "admin_password" not in result and result["admin_password_file"] == str(target)
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
    assert len(target.read_text().strip()) >= 20
    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        _apply(_config(), password_file=str(target))
    assert target.read_text().strip() != ""  # untouched


def test_second_run_with_the_same_config_creates_nothing_and_shows_no_password():
    cfg = _config()
    first = _apply(cfg)
    second = _apply(cfg)
    assert first["created"] is True and second["created"] is False and "admin_password" not in second
    assert second["organization_id"] == first["organization_id"] and _org_count(cfg["organization_name"]) == 1


def test_conflicts_and_bad_config_are_refused_with_a_clear_message():
    cfg = _config()
    _apply(cfg)
    with pytest.raises(SystemExit, match="idempotency_key_conflict"):
        _apply(dict(cfg, sector="Other"))
    with pytest.raises(SystemExit, match="organization_name_taken"):
        _apply(_config(organization_name=cfg["organization_name"]))
    with pytest.raises(SystemExit, match="Unknown config keys: nope"):
        _apply(dict(_config(), nope=1))
    with pytest.raises(SystemExit, match="Missing config keys"):
        _apply({"organization_name": "x"})
