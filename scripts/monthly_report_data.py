"""
Read-only counts for one tenant's monthly usage report (Batch Q, Q1).

Usage (production, as root in /opt/valqeron, with the real .env):
    venv/bin/python scripts/monthly_report_data.py --org 1 --month 2026-09 --out report.json

Only SELECT with COUNT/GROUP BY. Writes nothing to the database, no audit row (Dennis decided
explicitly: no). Only counts and statuses — never run output, document names, usernames, e-mail
addresses, amounts, candidates or free text. See the hand-off's own rule: a figure that would
have to come from free text or from a run's own output is refused, not worked around.

Known, explicitly reported gap (see claude-code-handoff-batch-q-maandrapportage.md's Fase 0):
WorkflowRun.status is only ever "ok" or "error" at the row level (app/workflows/services/
runner.py) — a workflow's own "degraded" result (PII anonymisation unavailable) lives only
inside output_payload, which is run output and therefore off-limits per the hand-off's own
rule. This script reports ok/error only; it does not count "degraded" separately.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import or_  # noqa: E402

from app.api.audit import _recompute_record_hash  # noqa: E402
from app.api.onboarding import PHASE_TITLES, _find_active_project  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.ai_incident import AIIncident  # noqa: E402
from app.models.ai_risk import AIRisk  # noqa: E402
from app.models.ai_system import AISystem  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.models.corrective_action import CorrectiveAction  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.onboarding_task import OnboardingTask  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.support_request import SupportRequest  # noqa: E402
from app.models.tenant_module import TenantModule  # noqa: E402
from app.models.workflow_run import WorkflowRun  # noqa: E402
from app.services.module_access import BASE_MODULES  # noqa: E402

_MODULE_BY_KEY = {m["key"]: m for m in BASE_MODULES}
_WORKFLOW_KEY_TO_MODULE_KEY = {m["workflow_key"]: m["key"] for m in BASE_MODULES if m.get("workflow_key")}


def parse_month(value: str) -> tuple[datetime.datetime, datetime.datetime, str]:
    try:
        year, month = (int(p) for p in value.split("-", 1))
    except Exception:
        raise SystemExit(f"--month must be YYYY-MM, got {value!r}")
    if not (1 <= month <= 12):
        raise SystemExit(f"--month must be YYYY-MM with a valid month, got {value!r}")
    start = datetime.datetime(year, month, 1)
    end = datetime.datetime(year + 1, 1, 1) if month == 12 else datetime.datetime(year, month + 1, 1)
    return start, end, f"{year:04d}-{month:02d}"


def check_period_is_closed(end: datetime.datetime, report_date: datetime.date) -> None:
    """The hand-off's periodecontrole: refuse unless the report date is strictly after the end
    of the period (i.e. the month has actually finished)."""
    if datetime.datetime.combine(report_date, datetime.time.min) < end:
        raise SystemExit(
            f"Refusing: report date {report_date.isoformat()} is not after the end of the "
            f"period ({end.date().isoformat()}). The month is not over yet."
        )


def collect(db, org_id: int, month: str) -> Dict[str, Any]:
    start, end, month_label = parse_month(month)
    report_date = datetime.date.today()
    check_period_is_closed(end, report_date)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise SystemExit(f"No organization with id {org_id}")

    active_modules = (
        db.query(TenantModule)
        .filter(TenantModule.organization_id == org_id, TenantModule.is_active.is_(True))
        .all()
    )
    active_module_keys = {m.module_key for m in active_modules}
    active_workflow_modules = [
        _MODULE_BY_KEY[k] for k in active_module_keys if k in _MODULE_BY_KEY and _MODULE_BY_KEY[k].get("workflow_key")
    ]

    # --- 2/3: runs per active module, ok/error (never "degraded" — see module docstring) ---
    runs_in_month = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.organization_id == org_id,
            WorkflowRun.created_at >= start,
            WorkflowRun.created_at < end,
        )
        .all()
    )
    per_module: Dict[str, Dict[str, Any]] = {}
    for m in active_workflow_modules:
        per_module[m["workflow_key"]] = {
            "module_key": m["key"],
            "module_name": m["name"],
            "workflow_key": m["workflow_key"],
            "ok": 0,
            "error": 0,
            "total": 0,
        }
    runs_total_all = 0
    runs_total_unmatched = 0  # runs under a workflow key that is not currently an active module
    for r in runs_in_month:
        runs_total_all += 1
        bucket = per_module.get(r.workflow)
        if bucket is None:
            runs_total_unmatched += 1
            continue
        bucket["total"] += 1
        if r.status == "ok":
            bucket["ok"] += 1
        elif r.status == "error":
            bucket["error"] += 1

    # --- 4: documents (only if Document Intelligence is active) ---
    documents_block: Optional[Dict[str, Any]] = None
    if "document_intelligence" in active_module_keys:
        total_documents = db.query(Document).filter(Document.organization_id == org_id).count()
        new_this_month = (
            db.query(Document)
            .filter(Document.organization_id == org_id, Document.created_at >= start, Document.created_at < end)
            .count()
        )
        documents_block = {"total": total_documents, "new_this_month": new_this_month}

    # --- 5: support requests submitted this month, and how many of those are now done ---
    requests_in_month = (
        db.query(SupportRequest)
        .filter(
            SupportRequest.organization_id == org_id,
            SupportRequest.created_at >= start,
            SupportRequest.created_at < end,
        )
        .all()
    )
    support_block = {
        "submitted_this_month": len(requests_in_month),
        "done_of_those": sum(1 for r in requests_in_month if r.status == "done"),
    }

    # --- 6: governance (point-in-time snapshot as of the report date, not month-windowed —
    #        matches how the Governance tab itself is presented: a current state, not a log) ---
    system_ids = [
        row[0]
        for row in db.query(AISystem.id).filter(AISystem.organization_id == org_id, AISystem.is_deleted.is_(False)).all()
    ]
    # .in_([]) compiles to an always-false clause in SQLAlchemy, so every query below is safe
    # even when system_ids (and therefore risk_ids/incident_ids) is empty — no Python branching.
    open_incidents = (
        db.query(AIIncident)
        .filter(AIIncident.ai_system_id.in_(system_ids), AIIncident.is_deleted.is_(False), AIIncident.status != "closed")
        .count()
    )
    risk_ids = [row[0] for row in db.query(AIRisk.id).filter(AIRisk.ai_system_id.in_(system_ids)).all()]
    incident_ids = [row[0] for row in db.query(AIIncident.id).filter(AIIncident.ai_system_id.in_(system_ids)).all()]
    linked_to_this_org = or_(
        CorrectiveAction.ai_risk_id.in_(risk_ids), CorrectiveAction.ai_incident_id.in_(incident_ids)
    )
    open_actions_q = db.query(CorrectiveAction).filter(CorrectiveAction.status != "closed", linked_to_this_org)
    open_actions = open_actions_q.count()
    overdue_actions = open_actions_q.filter(
        CorrectiveAction.due_date.isnot(None), CorrectiveAction.due_date < report_date
    ).count()
    governance_block = {
        "open_incidents": open_incidents,
        "open_corrective_actions": open_actions,
        "overdue_corrective_actions": overdue_actions,
        "ai_systems": len(system_ids),
        "ai_risks": db.query(AIRisk).filter(AIRisk.ai_system_id.in_(system_ids), AIRisk.is_deleted.is_(False)).count(),
    }

    # --- 7: audit log ---
    audit_rows_month = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.timestamp >= start, AuditLog.timestamp < end)
        .count()
    )
    all_audit_rows = db.query(AuditLog).filter(AuditLog.organization_id == org_id).order_by(AuditLog.id.asc()).all()
    mismatches = sum(1 for row in all_audit_rows if row.record_hash and _recompute_record_hash(row) != row.record_hash)
    audit_block = {
        "actions_this_month": audit_rows_month,
        "chain_status": "valid" if mismatches == 0 else "invalid",
    }

    # --- 8: onboarding (only while the project is still active/paused) ---
    onboarding_block: Optional[Dict[str, Any]] = None
    project = _find_active_project(db, org_id)
    if project is not None:
        tasks = (
            db.query(OnboardingTask)
            .filter(OnboardingTask.project_id == project.id, OnboardingTask.customer_visible.is_(True))
            .all()
        )
        phase_counts: Dict[int, Dict[str, Any]] = {}
        for t in tasks:
            p = phase_counts.setdefault(
                t.phase, {"phase": t.phase, "title": PHASE_TITLES.get(t.phase, f"Phase {t.phase}"), "total": 0, "done": 0}
            )
            p["total"] += 1
            if t.status in ("done", "skipped"):
                p["done"] += 1
        onboarding_block = {"phases": [phase_counts[k] for k in sorted(phase_counts)]}

    return {
        "organization": {"id": org.id, "name": org.name, "tier": org.tier},
        "period": {"month": month_label, "start": start.isoformat(), "end": end.isoformat()},
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "runs": {
            "total_this_month": runs_total_all,
            "total_unmatched_module": runs_total_unmatched,
            "per_module": list(per_module.values()),
        },
        "documents": documents_block,
        "support_requests": support_block,
        "governance": governance_block,
        "audit": audit_block,
        "onboarding": onboarding_block,
        "notes": {
            "degraded_not_counted": (
                "WorkflowRun.status is only ever 'ok' or 'error' at the row level; a 'degraded' "
                "result exists only inside a run's own output, which this script does not read. "
                "Degraded runs are counted as 'ok' here, same as the existing /workflows/dashboard "
                "endpoint — see the hand-off's Fase 0 for the full explanation."
            )
        },
    }


def print_readable(data: Dict[str, Any]) -> None:
    org = data["organization"]
    print(f"Organization: {org['name']} (id={org['id']}, tier={org['tier']})")
    print(f"Period: {data['period']['month']}")
    print(f"Runs this month: {data['runs']['total_this_month']} (unmatched module: {data['runs']['total_unmatched_module']})")
    for m in data["runs"]["per_module"]:
        print(f"  - {m['module_name']}: {m['total']} total ({m['ok']} ok, {m['error']} error)")
    if data["documents"] is not None:
        print(f"Documents: {data['documents']['total']} total, {data['documents']['new_this_month']} new this month")
    sr = data["support_requests"]
    print(f"Support requests: {sr['submitted_this_month']} submitted this month, {sr['done_of_those']} done")
    gov = data["governance"]
    print(
        f"Governance: {gov['open_incidents']} open incidents, {gov['open_corrective_actions']} open "
        f"corrective actions ({gov['overdue_corrective_actions']} overdue), {gov['ai_systems']} AI "
        f"systems, {gov['ai_risks']} risks"
    )
    audit = data["audit"]
    print(f"Audit: {audit['actions_this_month']} actions this month, chain {audit['chain_status']}")
    if data["onboarding"] is not None:
        print("Onboarding:")
        for p in data["onboarding"]["phases"]:
            print(f"  - Phase {p['phase']} ({p['title']}): {p['done']}/{p['total']}")
    else:
        print("Onboarding: no active project")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, type=int)
    parser.add_argument("--month", required=True)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        data = collect(db, args.org, args.month)
    finally:
        db.close()

    print_readable(data)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"\nwrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
