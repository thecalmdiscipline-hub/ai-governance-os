"""Tests for scripts/monthly_report_data.py (Batch Q, Q1).

Isolated org/system/risk/etc. fixtures per test (not the ambient dennis_admin/customer2_admin
demo state) — same pattern as tests/test_onboarding_progress.py and friends.
"""
import datetime
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from app.db.session import SessionLocal  # noqa: E402
from app.models.ai_incident import AIIncident  # noqa: E402
from app.models.ai_risk import AIRisk  # noqa: E402
from app.models.ai_system import AISystem  # noqa: E402
from app.models.corrective_action import CorrectiveAction  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.support_request import SupportRequest  # noqa: E402
from app.models.tenant_module import TenantModule  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workflow_run import WorkflowRun  # noqa: E402

import monthly_report_data as mrd  # noqa: E402


def _new_org(modules=("core",)):
    db = SessionLocal()
    org = Organization(name=f"report-test-{uuid.uuid4().hex[:10]}", tier="starter")
    db.add(org)
    db.commit()
    org_id = org.id
    for key in modules:
        db.add(TenantModule(organization_id=org_id, module_key=key, is_active=True))
    db.commit()
    db.close()
    return org_id


def _this_months_start():
    today = datetime.date.today()
    return datetime.datetime(today.year, today.month, 1)


def _last_full_month_label() -> str:
    today = datetime.date.today()
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"


def _last_full_month_bounds():
    label = _last_full_month_label()
    return mrd.parse_month(label)[:2] + (label,)


# ---------- check_period_is_closed ----------

def test_period_check_rejects_the_current_month():
    _, end, _ = mrd.parse_month(datetime.date.today().strftime("%Y-%m"))
    with pytest.raises(SystemExit):
        mrd.check_period_is_closed(end, datetime.date.today())


def test_period_check_accepts_a_month_that_has_fully_passed():
    start, end, _ = _last_full_month_bounds()
    mrd.check_period_is_closed(end, datetime.date.today())  # must not raise


def test_period_check_accepts_a_report_date_exactly_on_the_period_end_date():
    # end is the exclusive boundary (midnight on the 1st of the next month) — a report_date of
    # that same calendar day means the full period has already elapsed, so this must be accepted.
    start, end, _ = _last_full_month_bounds()
    mrd.check_period_is_closed(end, end.date())  # must not raise


def test_period_check_rejects_a_report_date_one_day_before_the_period_end():
    start, end, _ = _last_full_month_bounds()
    with pytest.raises(SystemExit):
        mrd.check_period_is_closed(end, end.date() - datetime.timedelta(days=1))


# ---------- parse_month ----------

def test_parse_month_rejects_a_malformed_value():
    with pytest.raises(SystemExit):
        mrd.parse_month("not-a-month")


def test_parse_month_rejects_month_13():
    with pytest.raises(SystemExit):
        mrd.parse_month("2026-13")


def test_parse_month_december_rolls_over_the_year():
    start, end, label = mrd.parse_month("2026-12")
    assert start == datetime.datetime(2026, 12, 1)
    assert end == datetime.datetime(2027, 1, 1)
    assert label == "2026-12"


# ---------- collect(): the empty-month case ----------

def test_empty_month_produces_a_valid_report_with_zeros():
    org_id = _new_org(modules=("core", "customer_support_ai"))
    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, _last_full_month_label())
    finally:
        db.close()

    assert data["runs"]["total_this_month"] == 0
    assert data["runs"]["total_unmatched_module"] == 0
    assert len(data["runs"]["per_module"]) == 1  # only customer_support_ai is a workflow module
    assert data["runs"]["per_module"][0]["ok"] == 0
    assert data["runs"]["per_module"][0]["error"] == 0
    assert data["documents"] is None  # document_intelligence not active
    assert data["support_requests"] == {"submitted_this_month": 0, "done_of_those": 0}
    assert data["governance"]["open_incidents"] == 0
    assert data["governance"]["ai_systems"] == 0
    assert data["audit"]["chain_status"] == "valid"  # no rows at all -> 0 mismatches -> valid
    assert data["onboarding"] is None  # no OpsAccount/project exists for this fresh org


def test_unknown_organization_id_is_rejected():
    db = SessionLocal()
    try:
        with pytest.raises(SystemExit):
            mrd.collect(db, 999_999_999, _last_full_month_label())
    finally:
        db.close()


# ---------- collect(): runs are correctly counted and bucketed ----------

def test_runs_are_counted_per_module_ok_and_error():
    org_id = _new_org(modules=("core", "customer_support_ai", "document_intelligence"))
    start, end, label = _last_full_month_bounds()
    mid_month = start + (end - start) / 2

    db = SessionLocal()
    db.add(WorkflowRun(run_id=f"r-{uuid.uuid4().hex[:8]}", workflow="customer_support", organization_id=org_id, status="ok", created_at=mid_month))
    db.add(WorkflowRun(run_id=f"r-{uuid.uuid4().hex[:8]}", workflow="customer_support", organization_id=org_id, status="error", created_at=mid_month))
    db.add(WorkflowRun(run_id=f"r-{uuid.uuid4().hex[:8]}", workflow="document_knowledge", organization_id=org_id, status="ok", created_at=mid_month))
    # outside the period — must not be counted
    db.add(WorkflowRun(run_id=f"r-{uuid.uuid4().hex[:8]}", workflow="customer_support", organization_id=org_id, status="ok", created_at=end + datetime.timedelta(days=1)))
    db.commit()
    db.close()

    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, label)
    finally:
        db.close()

    by_key = {m["workflow_key"]: m for m in data["runs"]["per_module"]}
    assert by_key["customer_support"]["ok"] == 1
    assert by_key["customer_support"]["error"] == 1
    assert by_key["customer_support"]["total"] == 2
    assert by_key["document_knowledge"]["ok"] == 1
    assert data["runs"]["total_this_month"] == 3  # the out-of-period row is excluded


def test_a_run_under_a_now_inactive_module_is_counted_as_unmatched_not_dropped_silently():
    org_id = _new_org(modules=("core",))  # customer_support_ai is NOT active
    start, end, label = _last_full_month_bounds()
    mid_month = start + (end - start) / 2

    db = SessionLocal()
    db.add(WorkflowRun(run_id=f"r-{uuid.uuid4().hex[:8]}", workflow="customer_support", organization_id=org_id, status="ok", created_at=mid_month))
    db.commit()
    db.close()

    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, label)
    finally:
        db.close()

    assert data["runs"]["total_this_month"] == 1
    assert data["runs"]["total_unmatched_module"] == 1
    assert data["runs"]["per_module"] == []  # no active workflow modules at all


# ---------- collect(): governance counts ----------

def test_open_incidents_and_corrective_actions_are_counted_correctly():
    org_id = _new_org(modules=("core",))
    db = SessionLocal()
    system = AISystem(name="Test system", organization_id=org_id)
    db.add(system)
    db.commit()

    open_incident = AIIncident(title="t1", severity="low", status="open", ai_system_id=system.id)
    closed_incident = AIIncident(title="t2", severity="low", status="closed", ai_system_id=system.id)
    deleted_incident = AIIncident(title="t3", severity="low", status="open", ai_system_id=system.id, is_deleted=True)
    db.add_all([open_incident, closed_incident, deleted_incident])
    db.commit()

    risk = AIRisk(title="r1", risk_level="medium", ai_system_id=system.id)
    db.add(risk)
    db.commit()

    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    overdue_action = CorrectiveAction(title="a1", description="d", status="open", ai_risk_id=risk.id, due_date=yesterday)
    not_overdue_action = CorrectiveAction(title="a2", description="d", status="open", ai_risk_id=risk.id, due_date=tomorrow)
    closed_action = CorrectiveAction(title="a3", description="d", status="closed", ai_risk_id=risk.id, due_date=yesterday)
    incident_linked_action = CorrectiveAction(title="a4", description="d", status="open", ai_incident_id=open_incident.id)
    db.add_all([overdue_action, not_overdue_action, closed_action, incident_linked_action])
    db.commit()
    db.close()

    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, _last_full_month_label())
    finally:
        db.close()

    gov = data["governance"]
    assert gov["open_incidents"] == 1  # closed and soft-deleted ones excluded
    assert gov["open_corrective_actions"] == 3  # overdue + not_overdue + incident_linked (closed excluded)
    assert gov["overdue_corrective_actions"] == 1
    assert gov["ai_systems"] == 1
    assert gov["ai_risks"] == 1


def test_governance_counts_are_zero_for_an_org_with_no_ai_systems():
    org_id = _new_org(modules=("core",))
    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, _last_full_month_label())
    finally:
        db.close()
    assert data["governance"] == {
        "open_incidents": 0,
        "open_corrective_actions": 0,
        "overdue_corrective_actions": 0,
        "ai_systems": 0,
        "ai_risks": 0,
    }


# ---------- collect(): documents only shown when the module is active ----------

def test_documents_block_is_none_when_document_intelligence_is_not_active():
    org_id = _new_org(modules=("core", "customer_support_ai"))
    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, _last_full_month_label())
    finally:
        db.close()
    assert data["documents"] is None


def test_documents_are_counted_when_the_module_is_active():
    org_id = _new_org(modules=("core", "document_intelligence"))
    start, end, label = _last_full_month_bounds()
    mid_month = start + (end - start) / 2

    db = SessionLocal()
    db.add(Document(organization_id=org_id, filename="a.txt", stored_name=f"s-{uuid.uuid4().hex}", path="/x", size=1, created_at=mid_month))
    db.add(Document(organization_id=org_id, filename="b.txt", stored_name=f"s-{uuid.uuid4().hex}", path="/x", size=1, created_at=end + datetime.timedelta(days=5)))
    db.commit()
    db.close()

    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, label)
    finally:
        db.close()

    assert data["documents"] == {"total": 2, "new_this_month": 1}


# ---------- collect(): support requests ----------

def test_support_requests_submitted_and_done_are_counted():
    org_id = _new_org(modules=("core",))
    start, end, label = _last_full_month_bounds()
    mid_month = start + (end - start) / 2

    db = SessionLocal()
    user = User(username=f"u-{uuid.uuid4().hex[:8]}", password_hash="x", role="admin", organization_id=org_id, is_active=True)
    db.add(user)
    db.commit()
    db.add(SupportRequest(reference=f"SR-{uuid.uuid4().hex[:8]}", organization_id=org_id, user_id=user.id, category="question", subject="s", message="m", status="done", created_at=mid_month))
    db.add(SupportRequest(reference=f"SR-{uuid.uuid4().hex[:8]}", organization_id=org_id, user_id=user.id, category="question", subject="s", message="m", status="new", created_at=mid_month))
    db.commit()
    db.close()

    db = SessionLocal()
    try:
        data = mrd.collect(db, org_id, label)
    finally:
        db.close()

    assert data["support_requests"] == {"submitted_this_month": 2, "done_of_those": 1}


# ---------- collect(): isolation between organizations ----------

def test_one_organizations_data_never_leaks_into_another():
    org_a = _new_org(modules=("core", "customer_support_ai"))
    org_b = _new_org(modules=("core", "customer_support_ai"))
    start, end, label = _last_full_month_bounds()
    mid_month = start + (end - start) / 2

    db = SessionLocal()
    db.add(WorkflowRun(run_id=f"r-{uuid.uuid4().hex[:8]}", workflow="customer_support", organization_id=org_a, status="ok", created_at=mid_month))
    db.commit()
    db.close()

    db = SessionLocal()
    try:
        data_a = mrd.collect(db, org_a, label)
        data_b = mrd.collect(db, org_b, label)
    finally:
        db.close()

    assert data_a["runs"]["total_this_month"] == 1
    assert data_b["runs"]["total_this_month"] == 0
