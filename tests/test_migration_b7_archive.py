"""Archive migration (96a4f064fbef), the separate last revision: on SQLite and PostgreSQL.

Fixtures (engine on both databases, temporary PostgreSQL) come from tests/test_migration_b7.py.
The chain before it is B1 -> B5 -> archive_download_enabled flag.
"""
from pathlib import Path

import sqlalchemy as sa

from tests.test_migration_b7 import CHAIN, _load, _run, engine, postgres_url  # noqa: F401  (fixtures)

ARCHIVE = "96a4f064fbef"


def _seed(engine, tmp_path):
    """Four documents, one per status the archive migration can meet, each with a real file on disk."""
    files = {}
    with engine.begin() as conn:
        for i, (name, status) in enumerate(
            [("a.txt", "uncoded"), ("b.txt", "coded"), ("c.txt", "archived"), ("d.txt", "uncoded")], start=1
        ):
            path = tmp_path / f"org_1_{name}"
            path.write_text(f"content {name}")
            files[i] = (str(path), path.read_bytes())
            conn.execute(sa.text(
                "INSERT INTO documents (id, organization_id, filename, stored_name, path, size, created_at, scope_status) "
                "VALUES (:id, 1, :fn, :sn, :p, 9, '2026-01-01', :st)"
            ), {"id": i, "fn": name, "sn": f"x_{name}", "p": str(path), "st": status})
        conn.execute(sa.text(
            "INSERT INTO document_scope_codes (document_id, code, created_at) VALUES (2, 'sales', '2026-01-01')"
        ))
    return files


def _rows(engine):
    with engine.begin() as conn:
        return {r.id: r for r in conn.execute(sa.text("SELECT * FROM documents ORDER BY id"))}


def _upgrade_to_before_archive(engine):
    for rev in CHAIN:
        _run(engine, _load(rev).upgrade)


def test_archive_migration_is_the_last_revision_after_the_flag():
    assert _load(ARCHIVE).down_revision == CHAIN[-1]


def test_archive_upgrade_archives_every_document_keeps_rows_and_files(engine, tmp_path):
    _upgrade_to_before_archive(engine)
    files = _seed(engine, tmp_path)
    before = _rows(engine)

    _run(engine, _load(ARCHIVE).upgrade)

    after = _rows(engine)
    assert len(after) == len(before) == 4
    assert {r.scope_status for r in after.values()} == {"archived"}
    assert {i: r.scope_status_before_archive for i, r in after.items()} == {
        1: "uncoded", 2: "coded", 3: None, 4: "uncoded",
    }
    for i, (path, content) in files.items():
        assert after[i].path == before[i].path == path  # no file moved
        assert Path(path).read_bytes() == content
    with engine.begin() as conn:  # codes are kept (V7: fixed once set)
        assert conn.execute(sa.text("SELECT code FROM document_scope_codes WHERE document_id=2")).scalar() == "sales"


def test_archive_downgrade_restores_saved_status_except_restored_documents(engine, tmp_path):
    _upgrade_to_before_archive(engine)
    _seed(engine, tmp_path)
    mig = _load(ARCHIVE)
    _run(engine, mig.upgrade)
    with engine.begin() as conn:  # document 4 was restored (archived -> coded) meanwhile
        conn.execute(sa.text("UPDATE documents SET scope_status='coded' WHERE id=4"))

    _run(engine, mig.downgrade)

    after = _rows(engine)
    assert {i: r.scope_status for i, r in after.items()} == {1: "uncoded", 2: "coded", 3: "archived", 4: "coded"}
    assert "scope_status_before_archive" not in {c["name"] for c in sa.inspect(engine).get_columns("documents")}


def test_archive_upgrade_on_empty_table(engine):
    _upgrade_to_before_archive(engine)
    _run(engine, _load(ARCHIVE).upgrade)
    assert _rows(engine) == {}
