"""Fase B3: document access per workflow (bouwopdracht §4, tests 4-8, 11, 12).

Every test uses its own organization, so ambient documents of org 1/2 never interfere.
"""
import uuid
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.models.organization import Organization
from app.services import document_access
from app.services.document_access import allowed_document_codes, load_scoped_documents, may_read
from app.services.document_scope_codes import WORKFLOW_SCOPE_CODES
from tests.conftest import ensure_document, mock_openai_response

ALL_WORKFLOWS = sorted(WORKFLOW_SCOPE_CODES)


@pytest.fixture()
def org_id():
    db = SessionLocal()
    try:
        org = Organization(name=f"scope-test-{uuid.uuid4().hex[:10]}")
        db.add(org)
        db.commit()
        return org.id
    finally:
        db.close()


def _doc(org_id, codes, body="Document body text.", status=None):
    stored = f"{uuid.uuid4().hex}_doc.txt"
    org_dir = Path(f"uploaded_documents/org_{org_id}")
    org_dir.mkdir(parents=True, exist_ok=True)
    path = org_dir / stored
    path.write_text(body, encoding="utf-8")
    doc = ensure_document(
        organization_id=org_id, uploaded_by_user_id=None, filename=stored, stored_name=stored,
        path=str(path), size=len(body), scope_codes=codes,
    )
    if status:
        db = SessionLocal()
        try:
            from app.models.document import Document
            row = db.get(Document, doc.id)
            row.scope_status = status
            db.commit()
        finally:
            db.close()
    return stored


def _visible(org_id, workflow_key, **kw):
    return {d["stored_name"] for d in load_scoped_documents(org_id, workflow_key, **kw)}


def test_allowed_document_codes_is_own_code_plus_shared():
    assert allowed_document_codes("sales_lead_qualification") == {"sales", "gedeeld"}
    assert allowed_document_codes("hr_recruitment") == {"hr", "gedeeld"}


def test_hr_document_is_never_read_by_a_non_hr_workflow(org_id):  # test 4
    hr_doc = _doc(org_id, ["hr"])
    for key in ALL_WORKFLOWS:
        if key == "hr_recruitment":
            continue
        assert hr_doc not in _visible(org_id, key), key
        assert hr_doc not in _visible(org_id, key, stored_names=[hr_doc]), key
    assert hr_doc in _visible(org_id, "hr_recruitment")


def test_document_knowledge_with_explicit_hr_selection_reads_nothing(org_id):  # test 4, end to end
    from app.workflows.implementations.document_knowledge import run

    hr_doc = _doc(org_id, ["hr"], body="Salary of candidate X is secret.")
    result = run(
        payload={"input": {"question": "What is the salary?", "documents": [hr_doc]}, "context": {}, "org_id": org_id},
        user_id=None,
    )
    assert result["answer"]["top_sources"] == []
    assert "secret" not in str(result)


def test_hr_recruitment_does_not_read_sales_document(org_id):  # test 5
    sales_doc = _doc(org_id, ["sales"])
    assert sales_doc not in _visible(org_id, "hr_recruitment")
    assert sales_doc in _visible(org_id, "sales_lead_qualification")


def test_shared_document_is_read_by_every_workflow(org_id):  # test 6
    shared = _doc(org_id, ["gedeeld"])
    for key in ALL_WORKFLOWS:
        assert shared in _visible(org_id, key), key


def test_document_with_own_code_and_shared_is_read_by_own_workflow_and_all_others(org_id):
    doc = _doc(org_id, ["sales", "gedeeld"])
    for key in ALL_WORKFLOWS:
        assert doc in _visible(org_id, key), key


def test_hr_combined_with_shared_is_never_read(org_id):
    # Refused at upload (B3a); defence in depth if such a row ever exists.
    doc = _doc(org_id, ["hr", "gedeeld"])
    for key in ALL_WORKFLOWS:
        assert doc not in _visible(org_id, key), key
    assert may_read("hr_recruitment", ["hr"]) is True
    assert may_read("hr_recruitment", ["hr", "gedeeld"]) is False


def test_uncoded_document_is_read_by_no_workflow(org_id):  # test 7
    doc = _doc(org_id, None)
    for key in ALL_WORKFLOWS:
        assert doc not in _visible(org_id, key), key


def test_archived_document_is_read_by_no_workflow(org_id):  # test 8
    doc = _doc(org_id, ["gedeeld"], status="archived")
    for key in ALL_WORKFLOWS:
        assert doc not in _visible(org_id, key), key


def test_limit_of_five_documents_and_6000_chars(org_id):  # V20
    for _ in range(7):
        _doc(org_id, ["kennis"], body="x" * 9000)
    docs = document_access.read_scoped_documents(org_id, "document_knowledge")
    assert len(docs) == 5
    assert all(len(d["text"]) == 6000 for d in docs)


def test_other_organization_documents_are_never_visible(org_id):
    other = _doc(org_id, ["gedeeld"])
    assert other not in _visible(org_id + 100000, "document_knowledge")


# --- V21: sales and compliance read documents, and still work without ------

def _capture_prompts(monkeypatch):
    from app.core import pii_anonymizer

    seen = []

    def _spy(text, workflow=None):
        seen.append(text)
        return text, {}

    monkeypatch.setattr(pii_anonymizer, "anonymize_text_with_mapping", _spy)
    return seen


def test_sales_lead_qualification_without_documents_still_gives_output(org_id, monkeypatch):  # test 11
    from app.workflows.implementations.sales_lead_qualification import run

    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    mock_openai_response(monkeypatch, {
        "score": 70, "qualification": "qualified", "summary": "Good fit.",
        "strengths": ["size"], "weaknesses": [], "next_actions": ["call"],
    })
    prompts = _capture_prompts(monkeypatch)
    result = run({"input": {"company": "Acme BV"}, "org_id": org_id}, user_id=None)
    assert result["status"] == "ok"
    assert result["score"] == 70
    assert "Reference documents" not in prompts[0]


def test_sales_lead_qualification_adds_in_scope_documents_to_prompt(org_id, monkeypatch):
    from app.workflows.implementations.sales_lead_qualification import run

    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    _doc(org_id, ["sales"], body="ICP: manufacturing, 50-500 employees.")
    _doc(org_id, ["hr"], body="HR secret salary list.")
    prompts = _capture_prompts(monkeypatch)
    run({"input": {"company": "Acme BV"}, "org_id": org_id}, user_id=None)
    assert "ICP: manufacturing" in prompts[0]
    assert "HR secret" not in prompts[0]


def test_compliance_monitoring_without_documents_still_gives_output(org_id, monkeypatch):  # test 12
    from app.workflows.implementations.compliance_monitoring import run

    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    mock_openai_response(monkeypatch, {
        "compliance_score": 60, "risk_level": "medium", "findings": [],
        "recommendations": ["Review."], "framework_alignment": [], "summary": "OK.",
    })
    prompts = _capture_prompts(monkeypatch)
    result = run({"input": {"policy_text": "All AI is reviewed."}, "org_id": org_id}, user_id=None)
    assert result["status"] == "ok"
    assert result["compliance_score"] == 60
    assert "Organisation documents" not in prompts[0]


def test_compliance_monitoring_adds_in_scope_documents_to_prompt(org_id, monkeypatch):
    from app.workflows.implementations.compliance_monitoring import run

    monkeypatch.setenv("OPENAI_API_KEY", "test-dummy-key")
    _doc(org_id, ["compliance"], body="Procedure: quarterly audit of all models.")
    _doc(org_id, ["marketing"], body="Campaign brief.")
    prompts = _capture_prompts(monkeypatch)
    run({"input": {"policy_text": "x"}, "org_id": org_id}, user_id=None)
    assert "quarterly audit" in prompts[0]
    assert "Campaign brief" not in prompts[0]
