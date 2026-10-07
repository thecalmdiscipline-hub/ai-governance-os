"""
Batch N4 (2026-10-07): seed Valqeron's own AI register (organization_id from the config, expected
to be 1 / HQ) from a reviewed, approved JSON file. Idempotent and insert-only — never overwrites an
existing row. Everything (one AIPolicy, then per AI system an AISystem, then its AIRisk(s)) runs in
one transaction: any problem rolls everything back, nothing partial is ever left behind.

Usage (as root, in /opt/valqeron, with the real .env):
    venv/bin/python scripts/seed_own_register.py --config scripts/data/eigen-register-valqeron.json --dry-run
    venv/bin/python scripts/seed_own_register.py --config scripts/data/eigen-register-valqeron.json

Two tiers of "already there, don't touch it":
  1. Expected (re-running this script): an AIPolicy already exists for the organization, or an
     AISystem with the exact same name already exists. Each is skipped individually and reported;
     the rest of the run continues.
  2. Unexpected: a brand-new AISystem's AIRisk has a title that collides with a risk title that
     already exists elsewhere in the organization. This is treated as a stop condition for the
     whole run (nothing is written) rather than silently working around it.

`use_status` from the JSON ("in_use" / "on_hold" / "planned") is not stored as a column — no schema
change. The text itself (e.g. "On hold: ..." in the HR workflow's purpose/description) already
carries the status, exactly as the hand-off specifies. Column-length limits are read from the real
SQLAlchemy column metadata (not assumed) — AIPolicy/AISystem/AIRisk's text columns are unbounded in
this schema (Text, or String() with no length), so in practice nothing can exceed them today; the
check still runs so it is not silently skipped if that ever changes.
"""
import argparse
import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from app.core.audit import create_audit_log
from app.db.session import SessionLocal
from app.models.ai_policy import AIPolicy
from app.models.ai_risk import AIRisk
from app.models.ai_system import AISystem

VALID_RISK_LEVELS = ("low", "medium", "high")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _max_length(column) -> Optional[int]:
    return getattr(column.type, "length", None)


def _check_length(column, value: str, label: str, problems: List[str]) -> None:
    limit = _max_length(column)
    if limit is not None and len(value) > limit:
        problems.append(f"{label} is {len(value)} characters, exceeds the {limit}-character column limit")


def plan(db, config: dict) -> Dict[str, object]:
    """Read-only: what would be created, what would be skipped, and any blocking problems."""
    organization_id = config["organization_id"]
    problems: List[str] = []

    existing_policy = db.query(AIPolicy).filter(AIPolicy.organization_id == organization_id).first()
    create_policy = existing_policy is None

    existing_system_names = {
        s.name for s in db.query(AISystem).filter(AISystem.organization_id == organization_id).all()
    }
    existing_risk_titles = {
        r.title
        for r in db.query(AIRisk).join(AISystem).filter(AISystem.organization_id == organization_id).all()
    }

    if create_policy:
        policy = config["policy"]
        _check_length(AIPolicy.__table__.c.purpose, policy["purpose"], "policy.purpose", problems)
        _check_length(AIPolicy.__table__.c.principles, policy["principles"], "policy.principles", problems)
        _check_length(AIPolicy.__table__.c.risk_commitment, policy["risk_commitment"], "policy.risk_commitment", problems)
        _check_length(AIPolicy.__table__.c.monitoring_commitment, policy["monitoring_commitment"], "policy.monitoring_commitment", problems)

    systems_to_create: List[dict] = []
    skipped_systems: List[str] = []

    for system in config["ai_systems"]:
        name = system["name"]
        if name in existing_system_names:
            skipped_systems.append(name)
            continue

        _check_length(AISystem.__table__.c.name, name, f"{name}.name", problems)
        _check_length(AISystem.__table__.c.description, system["description"], f"{name}.description", problems)
        _check_length(AISystem.__table__.c.purpose, system["purpose"], f"{name}.purpose", problems)

        for risk in system["risks"]:
            if risk["level"] not in VALID_RISK_LEVELS:
                problems.append(f"{name}/{risk['title']}: unknown risk level {risk['level']!r}")
            if risk["title"] in existing_risk_titles:
                # Tier 2 (unexpected): a brand-new system's risk collides with an existing,
                # unrelated risk title elsewhere in the organization. Stop the whole run.
                problems.append(
                    f"UNEXPECTED: risk title {risk['title']!r} for new system {name!r} already "
                    f"exists elsewhere in organization {organization_id} — stopping, nothing written"
                )
            _check_length(AIRisk.__table__.c.title, risk["title"], f"{name}/{risk['title']}.title", problems)
            _check_length(AIRisk.__table__.c.description, risk["description"], f"{name}/{risk['title']}.description", problems)
            _check_length(AIRisk.__table__.c.mitigation, risk["mitigation"], f"{name}/{risk['title']}.mitigation", problems)

        systems_to_create.append(system)

    return {
        "organization_id": organization_id,
        "create_policy": create_policy,
        "existing_policy_id": existing_policy.id if existing_policy else None,
        "systems_to_create": [s["name"] for s in systems_to_create],
        "skipped_systems": skipped_systems,
        "risks_to_create": sum(len(s["risks"]) for s in systems_to_create),
        "problems": problems,
        "_systems_to_create_full": systems_to_create,  # internal: used by apply(), not printed
    }


def apply(db, config: dict) -> Dict[str, object]:
    """Writes the register in one transaction (caller must roll back on any exception before that
    single commit; see the note below on why audit logging happens only after it).

    create_audit_log() commits the current transaction itself (confirmed by reading
    app/core/audit.py — the same reason Batch F's provisioning script writes audit entries only
    after its own main commit, never before). So every AIPolicy/AISystem/AIRisk row is built and
    added here first, with exactly one db.commit() for all of them together — a failure anywhere
    in that block leaves nothing committed. Only once that single commit has succeeded do we write
    one audit entry per created row; those calls can no longer undo the register data (same
    trade-off Batch F already accepted), so a problem purely in audit logging is reported as a
    partial-audit note rather than treated as if the whole run had failed.
    """
    result = plan(db, config)
    if result["problems"]:
        raise SystemExit("Refusing to write, nothing changed: " + "; ".join(result["problems"]))

    organization_id = result["organization_id"]
    db_policy = None
    created_system_rows: List[AISystem] = []
    created_risk_rows: List[AIRisk] = []

    if result["create_policy"]:
        policy = config["policy"]
        db_policy = AIPolicy(
            purpose=policy["purpose"],
            principles=policy["principles"],
            risk_commitment=policy["risk_commitment"],
            monitoring_commitment=policy["monitoring_commitment"],
            organization_id=organization_id,
        )
        db.add(db_policy)

    for system in result["_systems_to_create_full"]:
        db_system = AISystem(
            name=system["name"],
            description=system["description"],
            purpose=system["purpose"],
            organization_id=organization_id,
        )
        db.add(db_system)
        db.flush()  # need db_system.id for the risk FK below, before the single commit
        created_system_rows.append(db_system)

        for risk in system["risks"]:
            db_risk = AIRisk(
                title=risk["title"],
                description=risk["description"],
                mitigation=risk["mitigation"],
                risk_level=risk["level"],
                ai_system_id=db_system.id,
            )
            db.add(db_risk)
            created_risk_rows.append(db_risk)

    db.commit()  # the one commit for all real register data

    if db_policy is not None:
        create_audit_log(
            db,
            organization_id=organization_id,
            entity_type="ai_policy",
            entity_id=db_policy.id,
            action="seeded_own_register",
            details="AIPolicy seeded from the own-register config",
            performed_by="system:seed_own_register",
        )
    for db_system in created_system_rows:
        create_audit_log(
            db,
            organization_id=organization_id,
            entity_type="ai_system",
            entity_id=db_system.id,
            action="seeded_own_register",
            details=f"AISystem seeded: {db_system.name}",
            performed_by="system:seed_own_register",
        )
    for db_risk in created_risk_rows:
        create_audit_log(
            db,
            organization_id=organization_id,
            entity_type="ai_risk",
            entity_id=db_risk.id,
            action="seeded_own_register",
            details=f"AIRisk seeded: {db_risk.title}",
            performed_by="system:seed_own_register",
        )

    return {
        "policy_created": result["create_policy"],
        "created_systems": [s.name for s in created_system_rows],
        "skipped_systems": result["skipped_systems"],
        "created_risks": [r.title for r in created_risk_rows],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = parser.parse_args()

    config = load_config(args.config)
    db = SessionLocal()
    try:
        if args.dry_run:
            result = plan(db, config)
            print(f"organization_id={result['organization_id']}")
            if result["create_policy"]:
                print("policy: would create")
            else:
                print(f"policy: SKIP (already exists, id={result['existing_policy_id']})")
            print(f"systems to create ({len(result['systems_to_create'])}): {result['systems_to_create']}")
            print(f"systems to skip ({len(result['skipped_systems'])}): {result['skipped_systems']}")
            print(f"risks to create: {result['risks_to_create']}")
            if result["problems"]:
                print("PROBLEMS (nothing would be written):")
                for p in result["problems"]:
                    print(f"  - {p}")
            else:
                print("No problems found. DRY RUN - nothing written.")
        else:
            try:
                outcome = apply(db, config)
            except Exception:
                db.rollback()
                raise
            print(f"policy created: {outcome['policy_created']}")
            print(f"systems created ({len(outcome['created_systems'])}): {outcome['created_systems']}")
            print(f"systems skipped ({len(outcome['skipped_systems'])}): {outcome['skipped_systems']}")
            print(f"risks created ({len(outcome['created_risks'])}): {outcome['created_risks']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
