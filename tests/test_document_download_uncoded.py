"""Download rule for uncoded documents (docs/bouwopdracht-download-uncoded.md, decision 25 Nov 2026).

An 'uncoded' document (old, never coded) is downloadable/previewable only by a Valqeron
administrator, also when archive_download_enabled is on; 'archived' follows B5b; 'coded' is unchanged.
Numbers refer to §2 T2 of that document.
"""
import uuid

import pytest

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from tests.test_document_b7 import _archived_doc, _set_archive_download
from tests.test_document_rights import (  # noqa: F401  (fixtures hq, customer and _env are reused)
    _env, _h, _mfa_token, _new_org, _token, _uncoded_doc, _upload, _user, client, customer, hq,
)

PATHS = ["download", "preview"]
ROLES = ["admin", "member", "auditor"]


@pytest.fixture()
def org():
    return _new_org("dl-uncoded")


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("path", PATHS)
def test_uncoded_flag_off_is_403(org, role, path):  # tests 1 and 8
    doc_id = _uncoded_doc(org)
    res = client.get(f"/documents/{doc_id}/{path}", headers=_h(_token(_user(org, role=role)[0])))
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "uncoded_download_disabled"


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("path", PATHS)
def test_uncoded_flag_on_is_still_403(org, role, path):  # tests 2 and 8
    _set_archive_download(org, True)
    doc_id = _uncoded_doc(org)
    res = client.get(f"/documents/{doc_id}/{path}", headers=_h(_token(_user(org, role=role)[0])))
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "uncoded_download_disabled"


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("path", PATHS)
def test_archived_flag_off_is_403(org, role, path):  # tests 3 and 8
    doc_id, _ = _archived_doc(org)
    res = client.get(f"/documents/{doc_id}/{path}", headers=_h(_token(_user(org, role=role)[0])))
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "archive_download_disabled"


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("path", PATHS)
def test_archived_flag_on_is_200(org, role, path):  # tests 4 and 8
    _set_archive_download(org, True)
    doc_id, _ = _archived_doc(org)
    res = client.get(f"/documents/{doc_id}/{path}", headers=_h(_token(_user(org, role=role)[0])))
    assert res.status_code == 200


@pytest.mark.parametrize("path,action", [("download", "uncoded_document_downloaded"),
                                         ("preview", "uncoded_document_previewed")])
def test_valqeron_admin_may_read_uncoded_with_audit_in_hq_and_customer(hq, org, path, action):  # test 5
    doc_id = _uncoded_doc(org)
    token = _mfa_token(_user(hq)[0], valqeron_admin=True)
    res = client.get(f"/documents/{doc_id}/{path}", headers=_h(token))
    assert res.status_code == 200
    if path == "download":
        assert res.content == b"legacy"

    db = SessionLocal()
    lines = db.query(AuditLog).filter(AuditLog.action == action).all()
    db.close()
    assert any(l.organization_id == hq and f"document {doc_id}" in l.details for l in lines)
    assert any(l.organization_id == org and f"document {doc_id}" in l.details for l in lines)


@pytest.mark.parametrize("path", PATHS)
def test_uncoded_document_of_other_organization_is_404(org, customer, path):  # test 6
    doc_id = _uncoded_doc(org)
    _set_archive_download(customer, True)
    res = client.get(f"/documents/{doc_id}/{path}", headers=_h(_token(_user(customer)[0])))
    assert res.status_code == 404


def test_valqeron_admin_without_mfa_gets_404_on_uncoded_of_a_customer(hq, org):
    doc_id = _uncoded_doc(org)
    name, _ = _user(hq, is_valqeron_admin=True)
    assert client.get(f"/documents/{doc_id}/download", headers=_h(_token(name))).status_code == 404


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("flag", [False, True])
def test_coded_document_is_unchanged(org, role, flag):  # tests 7 and 8
    _set_archive_download(org, flag)
    uploader = _token(_user(org)[0])
    doc_id = _upload(uploader, name=f"[scope=kennis] coded-{uuid.uuid4().hex[:6]}.txt").json()["document"]["id"]
    token = _token(_user(org, role=role)[0])
    assert client.get(f"/documents/{doc_id}/download", headers=_h(token)).status_code == 200
    assert client.get(f"/documents/{doc_id}/preview", headers=_h(token)).status_code == 200
    assert client.get(f"/documents/{doc_id}", headers=_h(token)).status_code == 200


def test_valqeron_admin_still_cannot_read_a_customers_coded_document(hq, org):
    uploader = _token(_user(org)[0])
    doc_id = _upload(uploader, name=f"[scope=kennis] live-{uuid.uuid4().hex[:6]}.txt").json()["document"]["id"]
    token = _mfa_token(_user(hq)[0], valqeron_admin=True)
    assert client.get(f"/documents/{doc_id}/download", headers=_h(token)).status_code == 404
