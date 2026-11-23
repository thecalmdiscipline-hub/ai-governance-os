"""Fase B2: scope-code parsing, validation and upload refusal (V1, V4, V5, V18)."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import document_scope_codes as codes_mod
from app.services.document_scope import (
    ScopeValidationError,
    effective_scope,
    parse_scope_from_content,
    parse_scope_from_filename,
    scopes_for_upload,
    validate_scopes,
)
from app.workflows.registry import WORKFLOWS

client = TestClient(app)


# --- pure functions ---------------------------------------------------------

def test_every_registered_workflow_has_a_scope_code_that_is_a_document_code():
    assert set(codes_mod.WORKFLOW_SCOPE_CODES) == set(WORKFLOWS)
    for code in codes_mod.WORKFLOW_SCOPE_CODES.values():
        assert code in codes_mod.ALLOWED_CODES
    assert codes_mod.SHARED_CODE in codes_mod.ALLOWED_CODES


def test_parse_scope_from_filename():
    assert parse_scope_from_filename("[scope=hr] Functieprofiel.pdf") == {"hr"}
    assert parse_scope_from_filename("[scope=sales, gedeeld] Prijslijst.txt") == {"sales", "gedeeld"}
    assert parse_scope_from_filename("Prijslijst.txt") is None
    assert parse_scope_from_filename("[scope=sales] [scope=bi] x.txt") is None
    assert parse_scope_from_filename(None) is None


def test_parse_scope_from_content_uses_first_non_empty_line():
    assert parse_scope_from_content("\n\n  scope: sales,gedeeld\nrest") == {"sales", "gedeeld"}
    assert parse_scope_from_content("Title\nscope: sales") is None
    assert parse_scope_from_content("") is None
    assert parse_scope_from_content("﻿scope: kennis\n") == {"kennis"}


@pytest.mark.parametrize("codes,error", [
    (set(), "scope_missing"),
    ({"onbekend"}, "scope_unknown"),
    ({"Sales"}, "scope_invalid_format"),
    ({"hr", "gedeeld"}, "scope_exclusive_combined"),
    ({"hr", "sales"}, "scope_exclusive_combined"),
])
def test_validate_scopes_refuses(codes, error):
    with pytest.raises(ScopeValidationError) as exc:
        validate_scopes(codes)
    assert exc.value.error == error


def test_validate_scopes_accepts_multiple_known_codes_and_hr_alone():
    validate_scopes({"sales", "gedeeld"})
    validate_scopes({"hr"})


def test_scopes_for_upload_requires_equal_codes_in_name_and_content():
    assert scopes_for_upload("[scope=sales] a.txt", "scope: sales\nx") == {"sales"}
    with pytest.raises(ScopeValidationError) as exc:
        scopes_for_upload("[scope=sales] a.txt", "scope: bi\nx")
    assert exc.value.error == "scope_mismatch"


def test_effective_scope_reads_database_codes():
    doc = SimpleNamespace(scope_codes=[SimpleNamespace(code="sales"), SimpleNamespace(code="gedeeld")])
    assert effective_scope(doc) == {"sales", "gedeeld"}
    assert effective_scope(SimpleNamespace(scope_codes=[])) == set()


# --- upload route -----------------------------------------------------------

def _token(username="dennis_admin", password="Admin123!"):
    res = client.post(
        "/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def _files_on_disk(org_id=1):
    d = Path(f"uploaded_documents/org_{org_id}")
    return set(p.name for p in d.iterdir()) if d.exists() else set()


def _upload(token, name, body, ctype="text/plain"):
    return client.post(
        "/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (name, BytesIO(body), ctype)},
    )


@pytest.mark.parametrize("name,body,error", [
    ("no_code.txt", b"plain text", "scope_missing"),                                  # test 1
    ("[scope=sales] name_only.txt", b"no scope line here", "scope_missing_in_content"),  # test 2
    ("content_only.txt", b"scope: sales\nbody", "scope_missing_in_filename"),
    ("[scope=onbekend] x.txt", b"scope: onbekend\nbody", "scope_unknown"),            # test 3
    ("[scope=sales] x.txt", b"scope: bi\nbody", "scope_mismatch"),
    ("[scope=hr,gedeeld] x.txt", b"scope: hr,gedeeld\nbody", "scope_exclusive_combined"),
])
def test_upload_is_refused_with_422_and_writes_nothing(name, body, error):
    token = _token()
    before = _files_on_disk()
    res = _upload(token, name, body)
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == error
    assert _files_on_disk() == before


def test_upload_with_codes_stores_them_as_coded():
    token = _token()
    res = _upload(token, "[scope=sales,gedeeld] prijslijst.txt", b"scope: sales,gedeeld\nBronze: 10 EUR")
    assert res.status_code == 200
    doc = res.json()["document"]
    assert doc["scope_status"] == "coded"
    assert doc["scope_codes"] == ["gedeeld", "sales"]


def test_upload_docx_reads_scope_from_first_paragraph():
    from docx import Document as DocxDocument

    buf = BytesIO()
    d = DocxDocument()
    d.add_paragraph("scope: compliance")
    d.add_paragraph("Beleid")
    d.save(buf)

    token = _token()
    res = _upload(
        token,
        "[scope=compliance] beleid.docx",
        buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert res.status_code == 200
    assert res.json()["document"]["scope_codes"] == ["compliance"]
