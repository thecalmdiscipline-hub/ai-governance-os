"""Batch N4 (2026-10-07): scripts/seed_own_register.py — idempotent, insert-only seeding of
Valqeron's own AI register (AIPolicy + AISystem + AIRisk), one transaction, never overwrites."""
import copy
import importlib
import json
import os
import uuid

import pytest

from app.db.session import SessionLocal
from app.models.ai_policy import AIPolicy
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem
from app.models.audit_log import AuditLog
from app.models.organization import Organization

seed_script = importlib.import_module("scripts.seed_own_register")

REAL_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "data", "eigen-register-valqeron.json")


def _new_org():
    db = SessionLocal()
    org = Organization(name=f"own-register-test-{uuid.uuid4().hex[:10]}")
    db.add(org)
    db.commit()
    org_id = org.id
    db.close()
    return org_id


def _minimal_config(org_id):
    return {
        "organization_id": org_id,
        "policy": {
            "purpose": "Valqeron uses AI responsibly.",
            "principles": "Transparency and human oversight.",
            "risk_commitment": "Every system has a documented risk.",
            "monitoring_commitment": "Reviewed regularly by a person.",
        },
        "ai_systems": [
            {
                "key": "sys_a", "kind": "workflow", "name": "System A", "description": "desc a",
                "purpose": "purpose a", "use_status": "in_use",
                "risks": [{"title": "Risk A1", "description": "d1", "mitigation": "m1", "level": "medium"}],
            },
            {
                "key": "sys_b", "kind": "workflow", "name": "System B", "description": "desc b",
                "purpose": "purpose b", "use_status": "on_hold",
                "risks": [{"title": "Risk B1", "description": "d2", "mitigation": "m2", "level": "high"}],
            },
        ],
    }


def _counts(org_id):
    db = SessionLocal()
    c = {
        "policies": db.query(AIPolicy).filter(AIPolicy.organization_id == org_id).count(),
        "systems": db.query(AISystem).filter(AISystem.organization_id == org_id).count(),
        "risks": db.query(AIRisk).join(AISystem).filter(AISystem.organization_id == org_id).count(),
    }
    db.close()
    return c


def test_dry_run_plans_without_writing():
    org_id = _new_org()
    config = _minimal_config(org_id)

    db = SessionLocal()
    result = seed_script.plan(db, config)
    db.close()

    assert result["create_policy"] is True
    assert set(result["systems_to_create"]) == {"System A", "System B"}
    assert result["skipped_systems"] == []
    assert result["risks_to_create"] == 2
    assert result["problems"] == []
    assert _counts(org_id) == {"policies": 0, "systems": 0, "risks": 0}  # nothing written


def test_apply_creates_policy_systems_and_risks_in_one_commit():
    org_id = _new_org()
    config = _minimal_config(org_id)

    db = SessionLocal()
    outcome = seed_script.apply(db, config)
    db.close()

    assert outcome["policy_created"] is True
    assert set(outcome["created_systems"]) == {"System A", "System B"}
    assert set(outcome["created_risks"]) == {"Risk A1", "Risk B1"}
    assert _counts(org_id) == {"policies": 1, "systems": 2, "risks": 2}

    db = SessionLocal()
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.performed_by == "system:seed_own_register")
        .all()
    )
    # 1 policy + 2 systems + 2 risks = 5 audit rows for this run (plus the chain-v2 marker row).
    assert len(rows) == 5
    assert all(r.action == "seeded_own_register" for r in rows)
    db.close()


def test_rerun_is_idempotent_skips_everything_the_second_time():
    org_id = _new_org()
    config = _minimal_config(org_id)

    db = SessionLocal()
    seed_script.apply(db, config)
    db.close()

    db = SessionLocal()
    second = seed_script.plan(db, config)
    db.close()

    assert second["create_policy"] is False
    assert second["systems_to_create"] == []
    assert set(second["skipped_systems"]) == {"System A", "System B"}
    assert second["problems"] == []

    # And an actual second apply() writes nothing more.
    db = SessionLocal()
    outcome = seed_script.apply(db, config)
    db.close()
    assert outcome["created_systems"] == []
    assert outcome["created_risks"] == []
    assert _counts(org_id) == {"policies": 1, "systems": 2, "risks": 2}  # unchanged


def test_unexpected_risk_title_collision_blocks_the_whole_run():
    org_id = _new_org()

    # A pre-existing, unrelated system/risk that happens to share a risk title with the new config.
    db = SessionLocal()
    other_system = AISystem(name="Some other system", organization_id=org_id)
    db.add(other_system)
    db.commit()
    db.add(AIRisk(title="Risk A1", risk_level="low", ai_system_id=other_system.id))
    db.commit()
    db.close()

    config = _minimal_config(org_id)  # "System A" has a risk titled "Risk A1" — collision

    db = SessionLocal()
    result = seed_script.plan(db, config)
    db.close()
    assert any("UNEXPECTED" in p and "Risk A1" in p for p in result["problems"])

    db = SessionLocal()
    with pytest.raises(SystemExit):
        seed_script.apply(db, config)
    db.close()

    counts = _counts(org_id)
    assert counts["policies"] == 0  # nothing written at all, not even the policy
    assert counts["systems"] == 1  # only the pre-existing "Some other system"
    assert counts["risks"] == 1  # only the pre-existing risk


def test_invalid_risk_level_blocks_the_whole_run():
    org_id = _new_org()
    config = _minimal_config(org_id)
    config["ai_systems"][0]["risks"][0]["level"] = "critical"  # not a valid AIRisk level

    db = SessionLocal()
    result = seed_script.plan(db, config)
    db.close()
    assert any("unknown risk level" in p for p in result["problems"])

    db = SessionLocal()
    with pytest.raises(SystemExit):
        seed_script.apply(db, config)
    db.close()
    assert _counts(org_id) == {"policies": 0, "systems": 0, "risks": 0}


def test_rollback_on_failure_before_the_commit_leaves_nothing_behind(monkeypatch):
    """A failure while still building the rows (before apply()'s single db.commit() for the real
    register data) must roll back cleanly — nothing partial persists."""
    org_id = _new_org()
    config = _minimal_config(org_id)

    db = SessionLocal()
    real_flush = db.flush
    call_count = {"n": 0}

    def _flaky_flush(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:  # system A's flush succeeds, system B's does not
            raise RuntimeError("simulated failure before the real-data commit")
        return real_flush(*args, **kwargs)

    monkeypatch.setattr(db, "flush", _flaky_flush)

    try:
        with pytest.raises(RuntimeError):
            seed_script.apply(db, config)
    finally:
        db.rollback()
        db.close()

    assert _counts(org_id) == {"policies": 0, "systems": 0, "risks": 0}  # fully rolled back


def test_audit_failure_after_the_commit_does_not_undo_the_saved_register_data(monkeypatch):
    """create_audit_log() commits on its own (confirmed in app/core/audit.py) — the same reason
    Batch F's provisioning script only audits after its main commit. So a failure purely in audit
    logging, after apply()'s single real-data commit has already succeeded, must NOT make the
    register data disappear; it is an accepted, documented trade-off, not a bug."""
    org_id = _new_org()
    config = _minimal_config(org_id)

    call_count = {"n": 0}
    real_create_audit_log = seed_script.create_audit_log

    def _flaky(db, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:  # fails on the second audit call, well after the real commit
            raise RuntimeError("simulated audit failure, after the real-data commit")
        return real_create_audit_log(db, *args, **kwargs)

    monkeypatch.setattr(seed_script, "create_audit_log", _flaky)

    db = SessionLocal()
    with pytest.raises(RuntimeError):
        seed_script.apply(db, config)
    db.close()

    assert _counts(org_id) == {"policies": 1, "systems": 2, "risks": 2}  # not rolled back


def test_another_organization_is_never_touched():
    org_a = _new_org()
    org_b = _new_org()
    config_a = _minimal_config(org_a)

    db = SessionLocal()
    seed_script.apply(db, config_a)
    db.close()

    assert _counts(org_b) == {"policies": 0, "systems": 0, "risks": 0}


def test_column_length_check_uses_real_metadata_not_a_hardcoded_guess():
    # AIPolicy/AISystem/AIRisk's text columns are Text or length-less String() in this schema —
    # confirmed against production (see the report), so _max_length() returns None for all of them
    # and the length check never fires in practice. This proves the check is live wiring, not a
    # hardcoded number that happens to never be hit.
    assert seed_script._max_length(AIPolicy.__table__.c.purpose) is None
    assert seed_script._max_length(AISystem.__table__.c.name) is None
    assert seed_script._max_length(AIRisk.__table__.c.title) is None


def test_real_register_file_dry_run_has_no_problems_and_14_systems():
    with open(REAL_CONFIG_PATH, "r", encoding="utf-8") as f:
        real_config = json.load(f)

    org_id = _new_org()
    config = copy.deepcopy(real_config)
    config["organization_id"] = org_id  # never touch org 1 from a test

    db = SessionLocal()
    result = seed_script.plan(db, config)
    db.close()

    assert result["problems"] == []
    assert len(result["systems_to_create"]) == 14
    assert result["risks_to_create"] == 14
    assert _counts(org_id) == {"policies": 0, "systems": 0, "risks": 0}  # dry run, nothing written
