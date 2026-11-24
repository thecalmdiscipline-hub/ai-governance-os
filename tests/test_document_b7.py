"""Fase B7: restoring archived documents (T2), scope suggestions (T3, V2), delete roles (T4).

Numbers refer to docs/bouwopdracht-fase-b7.md §3. Tests 1-2 (the migration on PostgreSQL and SQLite)
are in tests/test_migration_b7_archive.py; test 14 (sales/compliance without documents) is covered by
tests/test_document_access.py and re-checked here.
"""
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.services import document_scope_rules
from app.services.document_access import load_scoped_documents
from app.services.document_scope_codes import WORKFLOW_SCOPE_CODES
from app.services.document_scope_rules import ScopeRulesError, load_rules, suggest_codes
from app.workflows.implementations.compliance_monitoring import run as run_compliance
from app.workflows.implementations.sales_lead_qualification import run as run_sales
from tests.conftest import ensure_document, mock_openai_response
from tests.test_document_rights import (  # noqa: F401  (fixtures hq, customer and _env are reused)
    _env, _new_org, _h, _mfa_token, _token, _upload, _user, client, customer, hq,
)

ALL_WORKFLOWS = sorted(WORKFLOW_SCOPE_CODES)


def _archived_doc(org_id, codes=None, before="uncoded"):
    """A document as the B7 migration leaves it: archived, with its previous status saved."""
    stored = f"{uuid.uuid4().hex}_old.txt"
    d = Path(f"uploaded_documents/org_{org_id}")
    d.mkdir(parents=True, exist_ok=True)
    (d / stored).write_text("Old document body.", encoding="utf-8")
    doc = ensure_document(organization_id=org_id, uploaded_by_user_id=None, filename=stored, stored_name=stored,
                          path=str(d / stored), size=18, scope_codes=codes)
    db = SessionLocal()
    row = db.get(Document, doc.id)
    row.scope_status = "archived"
    row.scope_status_before_archive = before
    db.commit()
    db.close()
    return doc.id, stored


def _state(document_id):
    db = SessionLocal()
    try:
        row = db.get(Document, document_id)
        return {"status": row.scope_status, "codes": sorted(c.code for c in row.scope_codes),
                "before": row.scope_status_before_archive}
    finally:
        db.close()


def _visible(org_id, workflow_key, **kw):
    return {d["stored_name"] for d in load_scoped_documents(org_id, workflow_key, **kw)}


# --- test 3: an archived document is read by no workflow ------------------------

@pytest.mark.parametrize("workflow_key", ALL_WORKFLOWS)
def test_archived_document_with_matching_code_is_read_by_no_workflow(customer, workflow_key):
    code = WORKFLOW_SCOPE_CODES[workflow_key]
    _, stored = _archived_doc(customer, codes=[code], before="coded")
    assert stored not in _visible(customer, workflow_key)
    assert stored not in _visible(customer, workflow_key, stored_names=[stored])


# --- T2: restore archived -> coded ----------------------------------------------

def test_valqeron_admin_restores_archived_document_and_workflow_reads_it(hq, customer):  # test 4
    doc_id, stored = _archived_doc(customer)
    token = _mfa_token(_user(hq)[0], valqeron_admin=True)

    res = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["sales"]}, headers=_h(token))
    assert res.status_code == 200
    assert res.json()["document"] == {"id": doc_id, "scope_status": "coded", "scope_codes": ["sales"]}
    assert _state(doc_id) == {"status": "coded", "codes": ["sales"], "before": None}
    assert stored in _visible(customer, "sales_lead_qualification")
    assert stored not in _visible(customer, "document_knowledge")


def test_customer_admin_cannot_restore(customer):  # test 5
    doc_id, _ = _archived_doc(customer)
    token = _token(_user(customer, role="admin")[0])
    assert client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis"]}, headers=_h(token)).status_code == 403
    assert _state(doc_id)["status"] == "archived"


def test_restore_with_unknown_code_is_422_and_stays_archived(hq, customer):  # test 6
    doc_id, _ = _archived_doc(customer)
    token = _mfa_token(_user(hq)[0], valqeron_admin=True)
    res = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["onbekend"]}, headers=_h(token))
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "scope_unknown"
    assert _state(doc_id) == {"status": "archived", "codes": [], "before": "uncoded"}


def test_restore_without_mfa_is_403(hq, customer):  # test 7
    doc_id, _ = _archived_doc(customer)
    name, _ = _user(hq, is_valqeron_admin=True)
    assert client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis"]},
                        headers=_h(_token(name))).status_code == 403
    assert _state(doc_id)["status"] == "archived"


def test_restore_writes_audit_line_in_hq_and_in_the_organization(hq, customer):  # test 8
    doc_id, _ = _archived_doc(customer)
    token = _mfa_token(_user(hq)[0], valqeron_admin=True)
    assert client.patch(f"/documents/{doc_id}/scope", json={"codes": ["kennis"]}, headers=_h(token)).status_code == 200

    db = SessionLocal()
    lines = db.query(AuditLog).filter(AuditLog.action == "document_scope_assigned").all()
    db.close()
    marker = f"document {doc_id}: archived -> coded"
    assert any(l.organization_id == hq and marker in l.details for l in lines)
    assert any(l.organization_id == customer and marker in l.details for l in lines)


def test_restore_keeps_existing_codes_fixed(hq, customer):  # V7
    doc_id, stored = _archived_doc(customer, codes=["support"], before="coded")
    token = _mfa_token(_user(hq)[0], valqeron_admin=True)

    other = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["sales"]}, headers=_h(token))
    assert other.status_code == 409
    assert other.json()["detail"]["error"] == "scope_fixed"
    assert _state(doc_id)["status"] == "archived"

    same = client.patch(f"/documents/{doc_id}/scope", json={"codes": ["support"]}, headers=_h(token))
    assert same.status_code == 200
    assert _state(doc_id) == {"status": "coded", "codes": ["support"], "before": None}
    assert stored in _visible(customer, "customer_support")


# --- T3: suggestions (V2) -------------------------------------------------------

def _blank_pdf():
    buf = BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.write(buf)
    return buf.getvalue()


def _suggest(token, name, body, ctype="text/plain"):
    return client.post("/documents/scope-suggestion", headers=_h(token), files={"file": (name, BytesIO(body), ctype)})


def test_pdf_without_text_layer_gets_no_suggestion_and_is_refused(customer):  # test 9
    token = _token(_user(customer, role="operator")[0])
    pdf = _blank_pdf()
    res = _suggest(token, "[scope=factuur] factuur-scan.pdf", pdf, "application/pdf")
    assert res.status_code == 200
    assert res.json()["readable"] is False and res.json()["suggested_codes"] == []

    up = _upload(token, name="[scope=factuur] factuur-scan.pdf", body=pdf)
    assert up.status_code == 422


def test_keyword_gives_suggestion_and_no_match_gives_empty_list(customer):  # test 10
    token = _token(_user(customer)[0])
    hit = _suggest(token, "januari.txt", b"Factuurnummer 2026-001\nTotaal 120 euro").json()
    assert hit["suggested_codes"] == ["factuur"] and hit["matched_rules"] == ["factuur"]

    miss = _suggest(token, "boodschappen.txt", b"melk, brood, kaas").json()
    assert miss["readable"] is True and miss["suggested_codes"] == [] and miss["matched_rules"] == []


def test_suggestion_stores_nothing(customer):
    token = _token(_user(customer)[0])
    db = SessionLocal()
    before = db.query(Document).filter(Document.organization_id == customer).count()
    db.close()
    _suggest(token, "notulen.txt", b"Notulen van de vergadering")
    db = SessionLocal()
    assert db.query(Document).filter(Document.organization_id == customer).count() == before
    db.close()


@pytest.mark.parametrize("role", ["auditor", "member"])
def test_suggestion_uses_upload_roles(customer, role):
    token = _token(_user(customer, role=role)[0])
    assert _suggest(token, "a.txt", b"factuur").status_code == 403


def test_upload_without_confirmed_code_is_422_even_with_a_suggestion(customer):  # test 11
    token = _token(_user(customer)[0])
    body = b"Factuurnummer 2026-002\nTotaal 99 euro"
    assert _suggest(token, "feb.txt", body).json()["suggested_codes"] == ["factuur"]
    res = _upload(token, name="feb.txt", body=body)
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "scope_missing"


def test_suggestion_for_document_type():
    rules = [{"name": "r", "document_types": ["csv"], "keywords": [], "codes": ["bi"]}]
    assert suggest_codes("cijfers.csv", "a,b\n1,2", rules)["suggested_codes"] == ["bi"]
    assert suggest_codes("cijfers.txt", "a,b\n1,2", rules)["suggested_codes"] == []


def test_shipped_rules_file_loads_and_is_used():
    assert document_scope_rules.RULES and document_scope_rules.RULES == load_rules()


def _rules_file(tmp_path, text):
    p = tmp_path / "rules.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_rules_with_unknown_code_fail_loudly(tmp_path):  # test 12
    p = _rules_file(tmp_path, "rules:\n  - name: fout\n    keywords: [x]\n    codes: [onbekend]\n")
    with pytest.raises(ScopeRulesError) as exc:
        load_rules(p)
    assert "fout" in str(exc.value) and "onbekend" in str(exc.value)


@pytest.mark.parametrize("text", [
    "rules:\n  - name: mix\n    keywords: [x]\n    codes: [hr, gedeeld]\n",
    "rules:\n  - name: leeg\n    codes: [kennis]\n",
    "rules:\n  - name: geen-codes\n    keywords: [x]\n",
    "rules:\n  - name: a\n    keywords: [x]\n    codes: [kennis]\n  - name: a\n    keywords: [y]\n    codes: [sales]\n",
    "rules:\n  - name: extra\n    keywords: [x]\n    codes: [kennis]\n    workflow: sales\n",
    "niet: [een, regellijst]\n",
    "rules: [\n",
])
def test_other_invalid_rules_files_fail_loudly(tmp_path, text):
    with pytest.raises(ScopeRulesError):
        load_rules(_rules_file(tmp_path, text))


def test_missing_rules_file_fails_loudly(tmp_path):
    with pytest.raises(ScopeRulesError):
        load_rules(tmp_path / "bestaat-niet.yaml")


# --- T4: delete roles -----------------------------------------------------------

@pytest.mark.parametrize("role", ["auditor", "member"])
def test_auditor_and_member_may_not_delete(customer, role):  # test 13
    admin = _token(_user(customer)[0])
    doc_id = _upload(admin, name=f"[scope=kennis] del-{uuid.uuid4().hex[:6]}.txt").json()["document"]["id"]
    res = client.delete(f"/documents/{doc_id}", headers=_h(_token(_user(customer, role=role)[0])))
    assert res.status_code == 403
    db = SessionLocal()
    assert db.get(Document, doc_id) is not None
    db.close()


@pytest.mark.parametrize("role", ["admin", "operator"])
def test_admin_and_operator_may_delete(customer, role):  # test 13
    token = _token(_user(customer, role=role)[0])
    doc_id = _upload(token, name=f"[scope=kennis] del-{uuid.uuid4().hex[:6]}.txt").json()["document"]["id"]
    res = client.delete(f"/documents/{doc_id}", headers=_h(token))
    assert res.status_code == 200 and res.json()["deleted"]["id"] == doc_id


# --- test 14: regression ----------------------------------------------------------

def test_sales_and_compliance_still_work_without_documents(monkeypatch):
    customer = _new_org("b7-empty")  # an organization without any document
    mock_openai_response(monkeypatch, {"score": 70, "summary": "ok", "strengths": [], "weaknesses": [],
                                       "next_actions": [], "compliance_score": 80, "risk_level": "low",
                                       "findings": [], "recommendations": [], "framework_alignment": []})
    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy")
    sales = run_sales({"input": {"lead": {"company": "Acme"}}, "org_id": customer})
    comp = run_compliance({"input": {"policy_text": "Policy"}, "org_id": customer})
    assert sales["status"] == "ok" and sales["sources"] == []
    assert comp["status"] == "ok" and comp["sources"] == []
