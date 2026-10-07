"""Batch N3 (2026-10-07): scripts/fix_monitoring_commitment.py — one-off correction of the old
monitoring_commitment overclaim, scoped to a single organization and only when the text is an
exact match."""
import importlib
import uuid

from app.core.provisioning_defaults import MONITORING_COMMITMENT_TEXT, STANDARD_NOTICE
from app.db.session import SessionLocal
from app.models.ai_policy import AIPolicy
from app.models.audit_log import AuditLog
from app.models.organization import Organization

fix_script = importlib.import_module("scripts.fix_monitoring_commitment")

OLD_TEXT = f"{STANDARD_NOTICE} AI systems are monitored continuously; incidents are recorded and followed up."
NEW_TEXT = f"{STANDARD_NOTICE} {MONITORING_COMMITMENT_TEXT}"


def _new_org():
    db = SessionLocal()
    org = Organization(name=f"fix-mc-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    org_id = org.id
    db.close()
    return org_id


def _policy_with_text(org_id, text):
    db = SessionLocal()
    policy = AIPolicy(purpose="p", principles="pr", risk_commitment="rc", monitoring_commitment=text, organization_id=org_id)
    db.add(policy)
    db.commit()
    policy_id = policy.id
    db.close()
    return policy_id


def test_dry_run_reports_without_writing():
    org_id = _new_org()
    policy_id = _policy_with_text(org_id, OLD_TEXT)

    db = SessionLocal()
    lines = fix_script.apply(db, org_id, dry_run=True)
    db.close()

    assert any(f"policy id={policy_id}" in line for line in lines)
    assert any(line.startswith("WOULD correct") for line in lines)

    db = SessionLocal()
    row = db.query(AIPolicy).filter(AIPolicy.id == policy_id).first()
    assert row.monitoring_commitment == OLD_TEXT  # untouched
    db.close()


def test_corrects_only_an_exact_match():
    org_id = _new_org()
    old_policy_id = _policy_with_text(org_id, OLD_TEXT)

    db = SessionLocal()
    lines = fix_script.apply(db, org_id, dry_run=False)
    db.close()

    assert any(f"policy id={old_policy_id}" in line and line.startswith("correct") for line in lines)

    db = SessionLocal()
    row = db.query(AIPolicy).filter(AIPolicy.id == old_policy_id).first()
    assert row.monitoring_commitment == NEW_TEXT
    db.close()


def test_skips_a_row_that_is_not_an_exact_match():
    org_id = _new_org()
    # Already corrected, or hand-edited by a client — either way, not the exact old text.
    policy_id = _policy_with_text(org_id, NEW_TEXT)

    db = SessionLocal()
    lines = fix_script.apply(db, org_id, dry_run=False)
    db.close()

    assert any(f"SKIPPED policy id={policy_id}" in line for line in lines)

    db = SessionLocal()
    row = db.query(AIPolicy).filter(AIPolicy.id == policy_id).first()
    assert row.monitoring_commitment == NEW_TEXT  # unchanged
    db.close()


def test_another_organizations_row_is_never_touched():
    org_a = _new_org()
    org_b = _new_org()
    policy_b = _policy_with_text(org_b, OLD_TEXT)

    db = SessionLocal()
    fix_script.apply(db, org_a, dry_run=False)  # org_a has no rows at all
    db.close()

    db = SessionLocal()
    row = db.query(AIPolicy).filter(AIPolicy.id == policy_b).first()
    assert row.monitoring_commitment == OLD_TEXT  # org_b's row, never touched by an org_a run
    db.close()


def test_idempotent_second_run_changes_nothing_more():
    org_id = _new_org()
    policy_id = _policy_with_text(org_id, OLD_TEXT)

    db = SessionLocal()
    fix_script.apply(db, org_id, dry_run=False)
    second_run_lines = fix_script.apply(db, org_id, dry_run=False)
    db.close()

    assert any(f"SKIPPED policy id={policy_id}" in line for line in second_run_lines)


def test_audit_log_has_no_policy_text():
    org_id = _new_org()
    policy_id = _policy_with_text(org_id, OLD_TEXT)

    db = SessionLocal()
    fix_script.apply(db, org_id, dry_run=False)
    row = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_type == "ai_policy", AuditLog.entity_id == policy_id)
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.action == "monitoring_commitment_corrected"
    assert row.performed_by == "system:fix_monitoring_commitment"
    assert "monitored continuously" not in (row.details or "")
    assert "reviewed on a regular basis" not in (row.details or "")
    db.close()
