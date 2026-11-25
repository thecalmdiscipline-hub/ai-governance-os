"""Fase B6: document_usage per run and the workflow_run_documents audit line (V19, test 10)."""
import uuid
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.document_usage import DocumentUsage
from app.models.organization import Organization
from app.models.workflow_run import WorkflowRun
from app.workflows.services.runner import run_workflow
from tests.conftest import ensure_document, mock_openai_response


@pytest.fixture()
def org_id():
    db = SessionLocal()
    try:
        org = Organization(name=f"usage-test-{uuid.uuid4().hex[:10]}")
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


def _doc(org_id, codes, body):
    stored = f"{uuid.uuid4().hex}_u.txt"
    d = Path(f"uploaded_documents/org_{org_id}")
    d.mkdir(parents=True, exist_ok=True)
    (d / stored).write_text(body, encoding="utf-8")
    return ensure_document(organization_id=org_id, uploaded_by_user_id=None, filename=stored, stored_name=stored,
                           path=str(d / stored), size=len(body), scope_codes=codes)


def _usage(run_id):
    db = SessionLocal()
    try:
        return sorted((u.document_id, u.codes) for u in db.query(DocumentUsage).filter(DocumentUsage.run_id == run_id))
    finally:
        db.close()


def _doc_audit(org_id):
    db = SessionLocal()
    try:
        return [a.details for a in db.query(AuditLog).filter(
            AuditLog.organization_id == org_id, AuditLog.action == "workflow_run_documents")]
    finally:
        db.close()


def test_run_writes_document_usage_and_audit_line(org_id, monkeypatch):  # test 10
    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    kennis = _doc(org_id, ["kennis"], "Opening hours 9-17.")
    shared = _doc(org_id, ["gedeeld"], "Company handbook.")
    _doc(org_id, ["hr"], "Salaries.")
    mock_openai_response(monkeypatch, {"answer": "9-17", "confidence": "high", "sources_used": [], "reasoning": "x"})

    result = run_workflow("document_knowledge", {"input": {"question": "Hours?"}, "context": {}}, user_id=None, org_id=org_id)
    assert result["status"] == "ok"

    assert _usage(result["run_id"]) == sorted([(kennis.id, "kennis"), (shared.id, "gedeeld")])
    lines = _doc_audit(org_id)
    assert len(lines) == 1
    assert kennis.filename in lines[0] and "[kennis]" in lines[0]
    assert shared.filename in lines[0] and "[gedeeld]" in lines[0]
    assert "Salaries" not in lines[0]


def test_run_without_documents_writes_audit_line_and_no_usage(org_id, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    result = run_workflow("compliance_monitoring", {"input": {"policy_text": "x"}, "context": {}}, user_id=None, org_id=org_id)
    assert result["status"] == "ok"
    assert _usage(result["run_id"]) == []
    assert _doc_audit(org_id) == ["Workflow compliance_monitoring read no documents"]


def test_workflow_that_reads_no_documents_writes_no_document_audit_line(org_id):
    result = run_workflow("customer_support", {"input": {"issue": "Login fails"}, "context": {}}, user_id=None, org_id=org_id)
    assert result["status"] == "ok"
    assert _doc_audit(org_id) == []


def test_usage_rows_belong_to_a_stored_run(org_id, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    _doc(org_id, ["sales"], "Price list.")
    result = run_workflow("sales_lead_qualification", {"input": {"company": "Acme"}, "context": {}}, user_id=None, org_id=org_id)
    db = SessionLocal()
    try:
        assert db.query(WorkflowRun).filter(WorkflowRun.run_id == result["run_id"]).count() == 1
    finally:
        db.close()
    assert len(_usage(result["run_id"])) == 1


def test_audit_chain_stays_valid_after_document_runs(org_id, monkeypatch):
    from app.api.audit import verify_audit_chain  # noqa: F401  (import check only)
    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    _doc(org_id, ["kennis"], "x")
    run_workflow("document_knowledge", {"input": {"question": "?"}, "context": {}}, user_id=None, org_id=org_id)

    from app.api import audit as audit_api
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.organization_id == org_id).order_by(AuditLog.id).all()
        assert rows, "expected audit rows"
        for row in rows:
            if row.record_hash:
                assert audit_api._recompute_record_hash(row) == row.record_hash
    finally:
        db.close()
